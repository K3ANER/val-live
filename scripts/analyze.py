"""Free VOD scanner: OCR text + image comparison on COLLECTION frames.

Only verifiable text or very close matches to Valorant-API icon artwork
in *two distinct frames* are marked verified. A one-frame hit is a candidate.
These techniques do not reliably identify a first-person 3D weapon view.
"""
from __future__ import annotations
import json
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PIL import Image, ImageEnhance, ImageOps
import pytesseract

from vision import ImageSkinMatcher, load_api_catalog

WEAPONS = ('Classic', 'Shorty', 'Frenzy', 'Ghost', 'Sheriff', 'Stinger', 'Spectre',
           'Bucky', 'Judge', 'Bulldog', 'Guardian', 'Phantom', 'Vandal', 'Marshal',
           'Outlaw', 'Operator', 'Ares', 'Odin', 'Melee')
COLLECTION_WORDS = ('collection', '컬렉션', 'skin collection', '스킨 컬렉션')
FRAME_INTERVAL_SECONDS = 8


def catalog_getter():
    with urllib.request.urlopen('https://valorant-api.com/v1/weapons/skins?language=en-US', timeout=25) as r:
        catalog = json.load(r)['data']
    result = {}
    for skin in catalog:
        name = skin.get('displayName', '')
        for weapon in WEAPONS:
            if name.lower().endswith(' ' + weapon.lower()) and not name.startswith('Standard '):
                result[name] = weapon
    return result


def norm(t):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', t.casefold()).split())


def match_skin(raw: str, catalog: dict[str, str]):
    normalized = ' ' + norm(raw) + ' '
    matches = []
    for full_name, weapon in catalog.items():
        n = norm(full_name)
        if len(n) >= 9 and ' ' + n + ' ' in normalized:
            matches.append({'weapon': weapon, 'skin': full_name})
    return matches


def is_collection(text: str):
    t = text.casefold()
    return any(word in t for word in COLLECTION_WORDS)


def segments(duration: int | None, window_sec=9 * 60, max_segments=3):
    if not duration:
        return [(0, window_sec), (30 * 60, 30 * 60 + window_sec), (60 * 60, 60 * 60 + window_sec)]
    if duration <= window_sec:
        return [(0, duration)]
    starts = [0, max(0, duration // 2 - window_sec // 2), max(0, duration - window_sec)]
    uniq = list(dict.fromkeys(starts))[:max_segments]
    return [(s, min(s + window_sec, duration)) for s in uniq]


def grab_frames(url: str, start: int, stop: int, work: Path):
    """Download only selected intervals; cannot bypass inaccessible/private VODs."""
    work.mkdir(parents=True, exist_ok=True)
    target = str(work / 'segment.%(ext)s')
    cmd = ['yt-dlp', '--no-playlist', '--no-warnings', '-f', 'b[height<=480]/b',
           '--download-sections', f'*{start}-{stop}', '--force-keyframes-at-cuts',
           '--merge-output-format', 'mp4', '--socket-timeout', '20', '-o', target, url]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=True)
    videos = [p for p in work.glob('segment.*') if p.suffix in ('.mp4', '.mkv', '.webm', '.ts')]
    if not videos:
        raise RuntimeError('VOD 구간을 내려받을 수 없습니다.')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(videos[0]),
                    '-vf', f'fps=1/{FRAME_INTERVAL_SECONDS},scale=1280:-1', '-q:v', '3',
                    str(work / 'frame_%05d.jpg')],
                   capture_output=True, text=True, timeout=120, check=True)
    return sorted(work.glob('frame_*.jpg'))


def _scan_frame_image(frame, catalog, vision_matcher, evidence, idx):
    """OCR serves as the collection-screen gate; vision recognizes icons."""
    try:
        with Image.open(frame) as image:
            ocr_view = ImageEnhance.Contrast(ImageOps.grayscale(image)).enhance(1.6)
            text = pytesseract.image_to_string(ocr_view, config='--psm 11')
            if not is_collection(text):
                return False
            matches = match_skin(text, catalog)
            if vision_matcher is not None:
                # Even if no full skin name is visible, try image recognition.
                try:
                    matches.extend(vision_matcher.recognize(image.convert('RGB'), text))
                except Exception:
                    pass
    except Exception:
        return False
    # Each frame contributes at most one hit for the same weapon+skin+method.
    seen = set()
    for m in matches:
        method = m.get('method', 'ocr_full_name')
        key = (m['weapon'], m['skin'], method)
        if key in seen:
            continue
        seen.add(key)
        entry = evidence.setdefault(key, {**m, 'frame_index': idx, 'hits': 0})
        entry['hits'] += 1
        # image recognition hit scores may differ slightly in separate frames
        if m.get('score', 0) > entry.get('score', 0):
            entry.update({k: v for k, v in m.items() if k in ('score', 'runner_up', 'image')})
    return True


def parse_frames(frames: list[Path], catalog: dict, vision_matcher=None):
    """Find skin text or image in separate collection frames (testable)."""
    evidence: dict[tuple, dict] = {}
    saw_collection = False
    for idx, frame in enumerate(frames):
        saw_collection |= _scan_frame_image(frame, catalog, vision_matcher, evidence, idx)
        if any(e['hits'] >= 2 for e in evidence.values()):
            break
    return saw_collection, list(evidence.values())


def scan_video(video, catalog: dict, *, getter: Callable = grab_frames,
               vision_matcher=None):
    when = datetime.now(timezone.utc).isoformat()
    result = {'player': video.player, 'url': video.url, 'title': video.title,
              'scanned_at': when, 'status': 'no_collection', 'candidates': [],
              'collection_seen': False, 'errors': []}
    accumulated: dict[tuple, dict] = {}
    # A candidate at the end of one segment can be corroborated in another.
    for start, stop in segments(video.duration):
        try:
            with tempfile.TemporaryDirectory(prefix='val-live-') as td:
                frames = getter(video.url, start, stop, Path(td))
                seen, candidates = parse_frames(frames, catalog, vision_matcher=vision_matcher)
            result['collection_seen'] |= seen
            for m in candidates:
                key = (m['weapon'], m['skin'], m.get('method', 'ocr_full_name'))
                timestamp = start + FRAME_INTERVAL_SECONDS * m['frame_index']
                found = accumulated.setdefault(key, {k: v for k, v in m.items() if k != 'frame_index'})
                if found is not m:
                    # First segment supplies its own hit count; later segments add.
                    if 'timestamp_seconds' in found:
                        found['hits'] += m['hits']
                found['timestamp_seconds'] = timestamp
                if m.get('score', 0) > found.get('score', 0):
                    found.update({k:v for k,v in m.items() if k in ('score','runner_up','image')})
            if any(v['hits'] >= 2 for v in accumulated.values()):
                break
        except Exception as e:
            result['errors'].append(str(e)[:220])
    result['candidates'] = sorted(accumulated.values(), key=lambda x: (x['hits'], x.get('score', 0)), reverse=True)[:12]
    if any(m['hits'] >= 2 for m in result['candidates']):
        result['status'] = 'verified'
    elif result['candidates']:
        result['status'] = 'candidate_found'
    elif result['collection_seen']:
        result['status'] = 'collection_no_text_or_image'
    else:
        result['status'] = 'error' if result['errors'] else 'no_collection'
    return result