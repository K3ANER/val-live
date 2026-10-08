"""Find actual public YouTube replays and Twitch VOD *files* without asking for links.

Never confuse a channel's /videos page for an actual playable VOD.
"""
from __future__ import annotations
import json
import re
import subprocess
from dataclasses import dataclass
from urllib.parse import urlsplit, parse_qs

@dataclass(frozen=True)
class Video:
    player: str
    url: str
    title: str
    origin: str
    duration: int | None = None
    upload_date: str | None = None

def call_ytdlp(url: str, *, timeout=75):
    command = [
        'yt-dlp','--no-warnings','--ignore-errors','--flat-playlist',
        '--playlist-end','8','--dump-single-json','--socket-timeout','12',url
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode or not result.stdout.strip():
        # Avoid dumping potentially signed provider video URLs to the website.
        raise RuntimeError('공개 방송 목록 접근 실패')
    return json.loads(result.stdout)

def canonical_video_url(platform: str, entry: dict) -> str | None:
    eid = str(entry.get('id') or '')
    raw = str(entry.get('webpage_url') or entry.get('url') or '')
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if platform == 'youtube':
        value = parse_qs(parsed.query).get('v',[''])[0]
        if parsed.hostname == 'youtu.be':
            value = parsed.path.strip('/')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{11}',value):
            value = eid
        if re.fullmatch(r'[a-zA-Z0-9_-]{11}', value):
            return 'https://www.youtube.com/watch?v=' + value
        return None
    if platform == 'twitch':
        match = re.fullmatch(r'/videos/(\d{6,})/?', parsed.path)
        if match and parsed.hostname in ('twitch.tv','www.twitch.tv'):
            return 'https://www.twitch.tv/videos/' + match.group(1)
        numeric = eid.lstrip('v')
        if re.fullmatch(r'\d{6,}', numeric):
            return 'https://www.twitch.tv/videos/' + numeric
        return None
    return None

def clean_entry(player: str, origin: str, entry: dict) -> Video | None:
    if not isinstance(entry,dict) or entry.get('_type')=='playlist':
        return None
    if entry.get('is_live') or entry.get('live_status') in ('is_live','is_upcoming'):
        return None
    host = (urlsplit(origin).hostname or '').lower()
    platform = 'twitch' if host in ('twitch.tv','www.twitch.tv') else 'youtube'
    url = canonical_video_url(platform,entry)
    if not url:
        return None
    duration=entry.get('duration')
    try: duration=int(duration) if duration is not None else None
    except (ValueError,TypeError): duration=None
    if duration is not None and duration<600:
        return None  # ignore very short non-VOD clips
    return Video(player, url, str(entry.get('title') or '라이브 다시보기')[:180],
                 origin, duration, str(entry.get('upload_date') or '') or None)

def discover_player(player: str, sources: list[str], *, fetch=call_ytdlp,
                    max_vods=2) -> tuple[list[Video],list[str]]:
    found=[]; errors=[]; seen=set()
    for origin in sources:
        try:
            info=fetch(origin)
            entries=info.get('entries') or ([info] if info.get('id') else [])
            for entry in entries:
                vid=clean_entry(player,origin,entry)
                if vid and vid.url not in seen:
                    seen.add(vid.url);found.append(vid)
                if len(found)>=max_vods:
                    break
            if len(found)>=max_vods:
                break
        except Exception as exc:
            errors.append(f'{origin}: {str(exc)[:110]}')
    return found[:max_vods], errors

def discover_all(sources: dict, *, fetch=call_ytdlp, max_vods=2):
    return {player:discover_player(player,channels,fetch=fetch,max_vods=max_vods)
            for player,channels in sources.items()}
