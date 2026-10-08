"""Runs on GitHub Actions: channel discovery -> replay scan -> safe JSON updates.

Do not erase previously verified loadouts if today's videos are unavailable.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from discover import discover_all
from analyze import catalog_getter, scan_video
from vision import ImageSkinMatcher, load_api_catalog

ROOT = Path(__file__).resolve().parents[1]


def read_json(file, fallback):
    try:
        return json.loads((ROOT / file).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return fallback


def write_json(file, data):
    (ROOT / file).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def run():
    sources = read_json('sources.json',{})
    latest = read_json('latest.json', {'schemaVersion':1,'players':{}})
    latest.setdefault('players',{})
    state = read_json('scan_state.json', {})
    history = read_json('history.json', [])
    now = datetime.now(timezone.utc).isoformat()
    selected = os.environ.get('PLAYER', 'all')
    if selected != 'all':
        sources = {selected: sources[selected]} if selected in sources else {}
    # Discover VOD urls automatically from broadcaster pages; frontend never asks for URLs.
    discoveries = discover_all(sources,max_vods=2)
    catalog = None
    vision_matcher = None
    vision_error = None
    event_log = []
    for player, (vods, errors) in discoveries.items():
        record = latest['players'].setdefault(player, {'weapons':{}})
        record.setdefault('weapons',{})
        record['channels'] = [{'label': 'Twitch' if 'twitch.tv' in u else 'YouTube', 'url': u.split('/videos?')[0].split('/streams')[0]}
                              for u in sources[player]]
        record['discoveredAt'] = now
        record['sourceCheck'] = {'status': 'vod_found' if vods else 'not_found',
                                 'message': f'자동 탐색: {len(vods)}개 공개 다시보기 발견' if vods else '공개 다시보기를 찾지 못했습니다.'}
        record['discoveredVods'] = [{'url':v.url,'title':v.title,'platform':'Twitch' if 'twitch.tv' in v.url else 'YouTube'} for v in vods]
        if errors:
            record['discoveryErrors'] = errors[:3]
        elif 'discoveryErrors' in record:
            record.pop('discoveryErrors')
        if vods:
            record['vod'] = {'url': vods[0].url, 'title':vods[0].title, 'publishedAt':vods[0].upload_date}
        for vod in vods:
            key = player + '|' + vod.url
            # Prevent expensive duplicate scans except explicit force, allowing periodic discovery of new streams.
            if key in state and not os.environ.get('FORCE_RESCAN'):
                continue
            if catalog is None:
                try:
                    catalog = catalog_getter()
                except Exception as e:
                    event_log.append({'player':player,'url':vod.url,'status':'error','error':'스킨 목록을 가져올 수 없음: '+str(e)[:150]})
                    break
            if vision_matcher is None and vision_error is None:
                try:
                    vision_matcher = ImageSkinMatcher(load_api_catalog())
                except Exception as e:
                    vision_error = str(e)[:200]
            result = scan_video(vod,catalog,vision_matcher=vision_matcher)
            if vision_error:
                result['vision_warning'] = '이미지 참조 목록 다운로드 실패: ' + vision_error
            state[key] = {'scanned_at':now,'status':result['status']}
            event_log.append(result)
            if result['status']=='verified':
                for c in result['candidates']:
                    if c.get('hits', 0)<2:
                        continue
                    record['weapons'][c['weapon']] = {
                        'skin':c['skin'],'verified':True,'source':vod.url,
                        'timestamp_seconds':c['timestamp_seconds'], 'checkedAt':now,
                        'method': c.get('method','ocr_full_name') + '_two_frames',
                        'image': c.get('image'), 'score': c.get('score')
                    }
                    record['checkedAt'] = now
                    record['sourceCheck'] = {'status':'verified','message':'다시보기 컬렉션의 2개 프레임에서 동일 스킨 이미지 또는 텍스트를 확인했습니다.'}
    write_json('latest.json',latest)
    write_json('scan_state.json',state)
    write_json('history.json',(event_log+history)[:60])
    print(json.dumps({'discovery':{p:len(v) for p,(v,_) in discoveries.items()},
                      'scans':len(event_log),'verified':sum(r.get('status')=='verified' for r in event_log)},ensure_ascii=False))


if __name__=='__main__':
    run()