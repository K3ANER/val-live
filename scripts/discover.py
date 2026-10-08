"""Discover public YouTube stream replays and Twitch VODs without a video URL."""
from __future__ import annotations
import json
import re
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse

@dataclass(frozen=True)
class Video:
    player: str
    url: str
    title: str
    origin: str
    duration: int | None = None
    upload_date: str | None = None

def call_ytdlp(url: str, *, timeout: int = 75) -> dict:
    cmd = ['yt-dlp','--no-warnings','--ignore-errors','--flat-playlist',
           '--playlist-end','4','--dump-single-json','--socket-timeout','15',url]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode or not proc.stdout.strip():
        raise RuntimeError((proc.stderr or 'Could not list videos')[-350:].strip())
    return json.loads(proc.stdout)

def clean_entry(player: str, origin: str, entry: dict) -> Video | None:
    if not isinstance(entry, dict) or entry.get('is_live') or entry.get('live_status') in {'is_live','is_upcoming'}:
        return None
    vid = str(entry.get('webpage_url') or entry.get('url') or '')
    eid = str(entry.get('id') or '')
    host = urlparse(origin).hostname or ''
    if not vid.startswith('https://'):
        if 'youtube.com' in host and re.fullmatch(r'[A-Za-z0-9_-]{11}', eid):
            vid = 'https://www.youtube.com/watch?v=' + eid
        elif 'twitch.tv' in host and eid.lstrip('v').isdigit():
            vid = 'https://www.twitch.tv/videos/' + eid.lstrip('v')
        else:
            return None
    vhost = (urlparse(vid).hostname or '').lower()
    if vhost not in {'www.youtube.com','youtube.com','www.twitch.tv','twitch.tv','youtu.be'}:
        return None
    if 'twitch.tv' in host and 'twitch.tv' not in vhost:
        return None
    if 'youtube.com' in host and vhost not in {'www.youtube.com','youtube.com','youtu.be'}:
        return None
    duration = entry.get('duration')
    try: duration = int(duration) if duration is not None else None
    except (TypeError,ValueError): duration = None
    if duration is not None and duration < 12*60:
        return None
    return Video(player=player, url=vid,title=str(entry.get('title') or '라이브 다시보기')[:180],
                 origin=origin,duration=duration,upload_date=str(entry.get('upload_date') or '') or None)

def discover_player(player: str, sources: list[str], *, fetch=call_ytdlp, max_vods: int = 2) -> tuple[list[Video], list[str]]:
    found=[]; errors=[]; seen=set()
    for url in sources:
        try:
            info=fetch(url)
            entries=info.get('entries') or ([info] if info.get('id') else [])
            for entry in entries:
                item=clean_entry(player,url,entry)
                if item and item.url not in seen:
                    found.append(item);seen.add(item.url)
                    break
        except Exception as e:
            errors.append(f'{url}: {str(e)[:160]}')
    return found[:max_vods],errors

def discover_all(sources: dict, *, fetch=call_ytdlp, max_vods=2):
    return {p:discover_player(p,channels,fetch=fetch,max_vods=max_vods) for p,channels in sources.items()}
