"""Speed-sampled public VOD analyzer. No paid vision service or realtime playback.

Phase 1: inspect one screenshot every 24 seconds for a recognizable VALORANT
gameplay HUD or the VALORANT COLLECTION screen. Other games are skipped.
Phase 2: sample a detected VALORANT segment every 4 seconds for COLLECTION
cards. Confirmed skin names require two distinct frames. Gameplay-only 3D
gun skins are not identified by the collection-card matcher.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PIL import Image, ImageEnhance, ImageOps
import pytesseract

WEAPONS = ('Classic', 'Shorty', 'Frenzy', 'Ghost', 'Sheriff', 'Stinger',
           'Spectre', 'Bucky', 'Judge', 'Bulldog', 'Guardian', 'Phantom',
           'Vandal', 'Marshal', 'Outlaw', 'Operator', 'Ares', 'Odin', 'Melee')
PROBE_INTERVAL_SECONDS = 24
DETAIL_INTERVAL_SECONDS = 4
WINDOW_SECONDS = 150
WINDOWS_PER_VIDEO = 5
COLLECTION_WORDS = ('collection', '컬렉션', 'skin collection', '스킨 컬렉션')
HUD_STRONG = (
    'buy phase', 'spike planted', 'spike defused', 'spike carrier',
    'combat report', 'ultimate ready', 'match point', 'switching sides',
    'enemy remaining', 'team ace', 'valorant',
)
HUD_PAIR = (
    'defenders', 'attackers', 'credits', 'spike', 'ability', 'kills',
    'vandal', 'phantom', 'sheriff', 'operator', 'spectre',
    'stinger', 'marshal', 'outlaw', 'bulldog', 'guardian',
)

def catalog_getter():
    with urllib.request.urlopen('https://valorant-api.com/v1/weapons/skins?language=en-US', timeout=25) as response:
        skins = json.load(response)['data']
    result = {}
    for skin in skins:
        name = skin.get('displayName', '')
        for weapon in WEAPONS:
            if name.lower().endswith(' ' + weapon.lower()) and not name.startswith('Standard '):
                result[name] = weapon
    return result

def norm(text):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', str(text).casefold()).split())

def match_skin(raw: str, catalog: dict[str, str]):
    normalized = ' ' + norm(raw) + ' '
    found = []
    for full_name, weapon in catalog.items():
        candidate = norm(full_name)
        if len(candidate) >= 9 and ' ' + candidate + ' ' in normalized:
            found.append({'weapon':weapon, 'skin':full_name})
    return found

def is_collection(text: str):
    lowered = str(text).casefold()
    return any(word in lowered for word in COLLECTION_WORDS)

def is_valorant_gameplay(text: str):
    """OCR HUD cue gate; one generic FPS gun name alone is insufficient."""
    lowered = norm(text)
    if not lowered:
        return False
    padded = ' ' + lowered + ' '
    if any(' ' + phrase + ' ' in padded for phrase in HUD_STRONG):
        return True
    cues = sum(' ' + word + ' ' in padded for word in HUD_PAIR)
    return cues >= 2 and any(' ' + word + ' ' in padded for word in ('defenders', 'attackers', 'spike', 'credits'))

def segments(duration: int | None, *, window_sec=WINDOW_SECONDS, max_segments=WINDOWS_PER_VIDEO):
    """Evenly spread short scan windows through long videos instead of replaying them."""
    if not duration or duration <= 0:
        starts = [0, 20 * 60, 45 * 60]
        return [(s, s + window_sec) for s in starts[:max_segments]]
    duration = int(duration)
    if duration <= window_sec:
        return [(0, duration)]
    width = min(window_sec, duration)
    end_start = max(0, duration - width)
    count = min(max_segments, max(2, (duration + 15 * 60 - 1) // (15 * 60)))
    starts = sorted(set(round(end_start * i / (count - 1)) for i in range(count)))
    return [(s, min(duration, s + width)) for s in starts]

def _find_segment(work: Path):
    return next((p for p in sorted(work.glob('segment.*'))
                 if p.suffix.lower() in ('.mp4', '.mkv', '.webm', '.ts')), None)

def grab_frames(url: str, start: int, stop: int, work: Path,
                *, interval=PROBE_INTERVAL_SECONDS, prefix='probe'):
    """Download a *short section once*, then extract frames locally at fast skip intervals.

    'Fast playback' here means sparse decoded screenshots, not playing at 1x.
    User need not open or upload a VOD.
    """
    work.mkdir(parents=True, exist_ok=True)
    segment = _find_segment(work)
    if segment is None:
        # Try different official yt-dlp clients and delivery formats.
        # Each attempt has a strict time bound; never claim success without a media file.
        strategies = [
            ('android', 'b[height<=480]/b', True),
            ('web_safari', 'b[height<=480]/b', True),
            ('default', 'bv*[height<=480]+ba/b', True),
            ('android', 'b[height<=480]/b', False),
        ]
        failures = []
        for client, fmt, section_only in strategies:
            for leftover in work.glob('segment.*'):
                leftover.unlink(missing_ok=True)
            command = [
                'yt-dlp', '--no-playlist', '--no-warnings', '--no-progress',
                '--js-runtimes', 'node', '--remote-components', 'ejs:npm',
                '--extractor-args', f'youtube:player_client={client}',
                '-f', fmt, '--merge-output-format', 'mp4',
                '--socket-timeout', '12', '--retries', '1',
                '--fragment-retries', '1',
                '-o', str(work / 'segment.%(ext)s'),
            ]
            if section_only:
                command += ['--download-sections', f'*{start}-{stop}']
            else:
                # Fallback: bounded download for short videos only.
                if stop > 180:
                    continue
                command += ['--max-filesize', '120M']
            command.append(url)
            try:
                result = subprocess.run(command, capture_output=True, text=True,
                                        timeout=100, check=False)
            except subprocess.TimeoutExpired:
                failures.append(client + ':timeout')
                continue
            segment = _find_segment(work)
            if result.returncode == 0 and segment is not None and segment.stat().st_size > 1024:
                break
            failures.append(client + (':403' if '403' in result.stderr else ':unavailable'))
            segment = None
        if segment is None:
            raise RuntimeError('유튜브 구간 추출 실패(시도: ' + ', '.join(failures) + ')')
    mask = str(work / f'{prefix}_%04d.jpg')
    command = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error',
        '-threads', '2', '-i', str(segment),
        '-vf', f'fps=1/{max(1,int(interval))},scale=960:-2',
        '-frames:v', '100', '-q:v', '4', mask
    ]
    try:
        subprocess.run(command, capture_output=True, text=True,
                       timeout=110, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('프레임 고속 추출 실패') from exc
    return sorted(work.glob(f'{prefix}_*.jpg'))

def read_frame_text(frame: Path):
    try:
        with Image.open(frame) as image:
            rgb = image.convert('RGB')
            gray = ImageOps.grayscale(rgb)
            enhanced = ImageEnhance.Contrast(gray).enhance(1.5)
            return pytesseract.image_to_string(enhanced, config='--psm 11')
    except Exception:
        return ''

def analyze_collection_frame(frame: Path, text: str, catalog: dict, matcher,
                             evidence: dict, *, frame_index: int, second: int):
    if not is_collection(text):
        return False
    matches = match_skin(text, catalog)
    # The visual matcher is costly: only invoke if OCR didn't read a skin name.
    if not matches and matcher is not None:
        try:
            with Image.open(frame) as image:
                matches.extend(matcher.recognize(image.convert('RGB'), text))
        except Exception:
            pass
    seen = set()
    for match in matches:
        method = match.get('method', 'ocr_full_name')
        key = (match['weapon'], match['skin'], method)
        if key in seen:
            continue
        seen.add(key)
        entry = evidence.setdefault(key, {
            'weapon':match['weapon'], 'skin':match['skin'],
            'method':method, 'hits':0,
            'timestamp_seconds':int(second),
            'frame_index':frame_index
        })
        entry['hits'] += 1
        if match.get('score', 0) > entry.get('score', 0):
            entry.update({k:v for k,v in match.items() if k in ('score','runner_up','image')})
    return True

def parse_frames(frames: list[Path], catalog: dict, vision_matcher=None):
    """Compatibility helper for unit tests; scores distinct collection frames."""
    evidence = {}
    saw_collection = False
    for idx, frame in enumerate(frames):
        text = read_frame_text(frame)
        saw_collection |= analyze_collection_frame(frame, text, catalog, vision_matcher,
                                                  evidence, frame_index=idx,
                                                  second=idx * DETAIL_INTERVAL_SECONDS)
        if any(v['hits'] >= 2 for v in evidence.values()):
            break
    return saw_collection, list(evidence.values())

def scan_video(video, catalog: dict, *, getter: Callable = grab_frames,
               vision_matcher=None):
    """Skip non-VALORANT sections at 24s intervals, refine VALORANT sections at 4s.

    A replay may contain multiple games. Keep scanning other windows if the first
    sampled window is unrelated. Stop when two collection images/texts agree.
    """
    result = {
        'player': video.player, 'url': video.url, 'title':video.title,
        'scanned_at':datetime.now(timezone.utc).isoformat(),
        'status':'no_valorant', 'candidates':[], 'collection_seen':False,
        'valorant_seen':False, 'frames_sampled':0, 'skipped_non_valorant_segments':0,
        'analysis_mode':'fast_valorant_only', 'probe_interval_seconds':PROBE_INTERVAL_SECONDS,
        'detail_interval_seconds':DETAIL_INTERVAL_SECONDS, 'errors':[]
    }
    evidence = {}
    for start, stop in segments(video.duration):
        try:
            with tempfile.TemporaryDirectory(prefix='val-live-fast-') as directory:
                work = Path(directory)
                probe_frames = getter(video.url, start, stop, work,
                                      interval=PROBE_INTERVAL_SECONDS, prefix='probe')
                # Scan HUD/collection text only; no expensive icon comparison here.
                eligible = False
                for frame in probe_frames:
                    text = read_frame_text(frame)
                    result['frames_sampled'] += 1
                    if is_valorant_gameplay(text) or is_collection(text):
                        eligible = True
                        result['valorant_seen'] = True
                        break
                if not eligible:
                    result['skipped_non_valorant_segments'] += 1
                    continue
                # Download happened already, just extract additional screenshots.
                detail_frames = getter(video.url, start, stop, work,
                                       interval=DETAIL_INTERVAL_SECONDS, prefix='detail')
                for i, frame in enumerate(detail_frames):
                    text = read_frame_text(frame)
                    result['frames_sampled'] += 1
                    if not is_collection(text):
                        continue  # Ignore gameplay HUD: collection card only.
                    result['valorant_seen'] = True
                    result['collection_seen'] |= analyze_collection_frame(
                        frame, text, catalog, vision_matcher, evidence,
                        frame_index=i, second=start + i * DETAIL_INTERVAL_SECONDS)
                    if any(v['hits'] >= 2 for v in evidence.values()):
                        break
        except Exception as exc:
            result['errors'].append(str(exc)[:190])
        if any(v['hits'] >= 2 for v in evidence.values()):
            break
    result['candidates'] = sorted(evidence.values(),
                                  key=lambda v:(v['hits'],v.get('score',0)),
                                  reverse=True)[:12]
    if any(v['hits']>=2 for v in result['candidates']):
        result['status']='verified'
    elif result['candidates']:
        result['status']='candidate_found'
    elif result['collection_seen']:
        result['status']='collection_no_text_or_image'
    elif result['valorant_seen']:
        result['status']='valorant_no_collection'
    elif result['errors'] and result['skipped_non_valorant_segments'] == 0:
        result['status']='error'
    else:
        result['status']='no_valorant'
    return result
