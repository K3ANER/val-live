"""Free, conservative image recognition for VALORANT *collection cards*.

Compares pixels of on-screen skin illustrations with the freely accessible
Valorant-API skin icon catalog using masked multi-scale normalized correlation.
It is NOT a general classifier for 3D first-person weapon models. To avoid
fabricated loadouts, an image finding needs two independent collection frames.
"""
from __future__ import annotations

import io
import json
import math
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PIL import Image

WEAPON_NAMES = ('Classic', 'Shorty', 'Frenzy', 'Ghost', 'Sheriff', 'Stinger',
                'Spectre', 'Bucky', 'Judge', 'Bulldog', 'Guardian', 'Phantom',
                'Vandal', 'Marshal', 'Outlaw', 'Operator', 'Ares', 'Odin', 'Melee')
API = 'https://valorant-api.com/v1/weapons?language=en-US'
ALLOWED_IMAGE_HOSTS = {'media.valorant-api.com'}
# Conservative acceptance: require both absolute similarity and a clear lead
# against other skins of the *same weapon*.
MIN_IMAGE_SCORE = 0.82
MIN_WINNER_MARGIN = 0.085
SEARCH_WIDTHS = (120, 160, 190, 230, 280)


@dataclass(frozen=True)
class SkinIcon:
    weapon: str
    skin: str
    url: str


def build_icon_catalog(api_weapons: list[dict]) -> dict[str, list[SkinIcon]]:
    """Use the weapon=>skin relationship, not a name-suffix heuristic."""
    refs: dict[str, list[SkinIcon]] = {w: [] for w in WEAPON_NAMES}
    for weapon_info in api_weapons:
        weapon = str(weapon_info.get('displayName', ''))
        if weapon not in refs:
            continue
        seen = set()
        for skin in weapon_info.get('skins') or []:
            name = str(skin.get('displayName') or '')
            if not name or name.casefold().startswith('standard '):
                continue
            # Default skin icon is typically identical to the collection item.
            levels = skin.get('levels') or []
            base = skin.get('displayIcon') or (levels[0].get('displayIcon') if levels else '')
            choices = [base]
            # Include two variant renders for common recolored loadouts without
            # needing a paid visual recognition API. Missing icons are harmless.
            for chroma in (skin.get('chromas') or [])[:2]:
                choices.append(chroma.get('displayIcon') or chroma.get('fullRender'))
            for url in choices:
                if not isinstance(url, str) or not valid_icon_url(url) or url in seen:
                    continue
                seen.add(url)
                refs[weapon].append(SkinIcon(weapon, name, url))
    return refs


def valid_icon_url(value: str) -> bool:
    try:
        u = urllib.parse.urlsplit(value)
        return u.scheme == 'https' and u.hostname in ALLOWED_IMAGE_HOSTS
    except ValueError:
        return False


def load_api_catalog() -> dict[str, list[SkinIcon]]:
    req = urllib.request.Request(API, headers={'User-Agent': 'VAL-LIVE/1.0'})
    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.load(response)['data']
    return build_icon_catalog(data)


def get_visible_weapons(text: str) -> list[str]:
    """Restrict expensive image search to weapon tabs visibly named by OCR."""
    return [w for w in WEAPON_NAMES if re.search(r'(?<![a-z])' + re.escape(w) + r'(?![a-z])', text, re.I)]


def download_image(url: str) -> Image.Image:
    if not valid_icon_url(url):
        raise ValueError('External icon host not permitted')
    req = urllib.request.Request(url, headers={'User-Agent': 'VAL-LIVE/1.0'})
    with urllib.request.urlopen(req, timeout=10) as response:
        content = response.read(3_000_001)
    if len(content) > 3_000_000:
        raise ValueError('Icon too large')
    return Image.open(io.BytesIO(content)).convert('RGBA')


def prepare_icon(icon: Image.Image) -> np.ndarray | None:
    rgba = np.asarray(icon.convert('RGBA'))
    alpha = rgba[:, :, 3]
    coords = np.nonzero(alpha > 80)
    if len(coords[0]) < 250:
        return None
    top, bottom = int(coords[0].min()), int(coords[0].max()) + 1
    left, right = int(coords[1].min()), int(coords[1].max()) + 1
    # Crop transparent outskirts so matching uses visible weapon artwork only.
    rgba = rgba[top:bottom, left:right]
    if rgba.shape[1] < 32 or rgba.shape[0] < 12:
        return None
    return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)


def template_score(frame_gray: np.ndarray, icon_bgra: np.ndarray,
                   widths: tuple[int, ...] = SEARCH_WIDTHS) -> float:
    """Find icon pixels anywhere on the collection screen, at UI display scales.

    Uses a transparent mask so card backgrounds do not have to match.
    The result is a raw 0..1 visual match score; it is not a probability.
    """
    frame_h, frame_w = frame_gray.shape[:2]
    h0, w0 = icon_bgra.shape[:2]
    best = 0.0
    checked = set()
    width_queue = list(widths)
    best_width = None
    for width in width_queue:
        if width in checked:
            continue
        checked.add(width)
        height = max(1, round(width * h0 / w0))
        if height > frame_h * .78 or width > frame_w * .85 or height < 12:
            continue
        resized = cv2.resize(icon_bgra, (width, height), interpolation=cv2.INTER_AREA if w0 > width else cv2.INTER_LINEAR)
        alpha = resized[:, :, 3]
        mask = (alpha > 165).astype(np.uint8) * 255
        if cv2.countNonZero(mask) < width * height * .12:
            continue
        template = cv2.cvtColor(resized[:, :, :3], cv2.COLOR_BGR2GRAY)
        # normalized CCOEFF with alpha mask suppresses background-only matches
        response = cv2.matchTemplate(frame_gray, template, cv2.TM_CCOEFF_NORMED, mask=mask)
        if response.size and np.isfinite(response).any():
            val = float(np.nanmax(response))
            if math.isfinite(val) and val > best:
                best = val
                best_width = width
        # A coarse positive triggers precise 2-pixel width refinement. This
        # also compensates for transparent borders and UI icon rescaling.
        if len(checked) == len(widths) and best_width is not None and best > 0.5:
            width_queue.extend(range(max(45, best_width - 12), best_width + 13, 2))
    return min(1., max(0., best))


class ImageSkinMatcher:
    """Match *collection artwork* against public skin icons; not gameplay views.

    The catalog and all icons are loaded lazily. A downloaded image is cached
    during the workflow run. `icon_loader` can be injected for unit tests.
    """
    def __init__(self, catalog: dict[str, list[SkinIcon]],
                 icon_loader: Callable[[str], Image.Image] = download_image,
                 *, widths: tuple[int, ...] = SEARCH_WIDTHS,
                 min_score: float = MIN_IMAGE_SCORE,
                 margin: float = MIN_WINNER_MARGIN):
        self.catalog = catalog
        self.loader = icon_loader
        self.widths = widths
        self.min_score = min_score
        self.margin = margin
        self._icons: dict[str, np.ndarray | None] = {}
        self._bad_urls: set[str] = set()

    def _get_icon(self, url: str) -> np.ndarray | None:
        if url in self._icons:
            return self._icons[url]
        if url in self._bad_urls:
            return None
        try:
            rgba = prepare_icon(self.loader(url))
            if rgba is None:
                self._bad_urls.add(url)
            else:
                self._icons[url] = rgba
            return rgba
        except Exception:
            self._bad_urls.add(url)
            return None

    def recognize(self, frame: Image.Image, ocr_text: str, *,
                  allowed_weapons: list[str] | None = None) -> list[dict]:
        """Return only a clear icon match; never pretend a score is 100% certain.

        Caller must first establish this is a collection screen, and must
        accumulate results across *two distinct* video frames before posting.
        """
        weapons = allowed_weapons if allowed_weapons is not None else get_visible_weapons(ocr_text)
        if not 1 <= len(weapons) <= 2:
            return []  # ambiguous navigation tabs -> do not infer a skin
        frame_rgb = frame.convert('RGB')
        if frame_rgb.width > 960:
            frame_rgb = frame_rgb.resize((960, round(frame_rgb.height * 960 / frame_rgb.width)))
        gray = cv2.cvtColor(np.array(frame_rgb), cv2.COLOR_RGB2GRAY)
        found = []
        for weapon in weapons:
            refs = self.catalog.get(weapon, [])
            # Keep the best variant score for each skin name (variants are not
            # different skins for the frontend loadout).
            scores: dict[str, tuple[float, str]] = {}
            for ref in refs:
                icon = self._get_icon(ref.url)
                if icon is None:
                    continue
                score = template_score(gray, icon, self.widths)
                if score > scores.get(ref.skin, (0.0, ''))[0]:
                    scores[ref.skin] = (score, ref.url)
            ordered = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)
            if not ordered:
                continue
            (skin, (score, url)) = ordered[0]
            runner_up = ordered[1][1][0] if len(ordered) > 1 else 0.0
            if score >= self.min_score and score - runner_up >= self.margin:
                found.append({'weapon':weapon, 'skin':skin, 'image':url,
                              'score':round(score, 4), 'runner_up':round(runner_up, 4),
                              'method':'image_template_match'})
        return found