"""Scheduled free VOD discovery, quick VALORANT-only scans and safe publication."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from discover import discover_all
from analyze import catalog_getter, scan_video
from vision import ImageSkinMatcher, load_api_catalog

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'latest-vod-priority-v2'

def read_json(name, default):
    try:
        return json.loads((ROOT / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default

def write_json(name, data):
    path=ROOT/name
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',
                    encoding='utf-8')

def should_scan(old, current_time, force=False):
    if force or not isinstance(old,dict) or old.get('revision')!=REVISION:
        return True
    if old.get('status') in ('verified','no_valorant','valorant_no_collection',
                              'collection_no_text_or_image','candidate_found'):
        return False
    try:
        last=datetime.fromisoformat(old['scanned_at'])
        return current_time-last >= timedelta(hours=24)
    except (KeyError,ValueError,TypeError):
        return True

def run():
    all_sources=read_json('sources.json',{})
    # Never scan all players in the same job; the scheduler chooses exactly one.
    selected=os.getenv('PLAYER','TenZ')
    if selected not in all_sources:
        raise SystemExit('Invalid player selection; only a single configured player is allowed.')
    sources={selected:all_sources[selected]}
    latest=read_json('latest.json',{'schemaVersion':1,'players':{}})
    latest.setdefault('players',{})
    state=read_json('scan_state.json',{})
    history=read_json('history.json',[])
    now=datetime.now(timezone.utc)
    now_stamp=now.isoformat()
    discovery=discover_all(sources,max_vods=1)
    catalog=None
    icon_matcher=None
    icon_warning=None
    events=[]
    force=os.environ.get('FORCE_RESCAN')=='1'
    for player,(vods,errors) in discovery.items():
        record=latest['players'].setdefault(player,{'weapons':{}})
        record.setdefault('weapons',{})
        record['channels']=[
            {'label':'Twitch' if 'twitch.tv' in origin else 'YouTube',
             'url':origin.split('/videos?')[0].split('/streams')[0]}
            for origin in sources[player]]
        record['discoveredAt']=now_stamp
        record['discoveredVods']=[
            {'url':v.url,'title':v.title,
             'platform':'Twitch' if 'twitch.tv' in v.url else 'YouTube'}
            for v in vods]
        if errors: record['discoveryErrors']=errors[:3]
        else: record.pop('discoveryErrors',None)
        if vods:
            record['vod']={'url':vods[0].url,
                           'title':vods[0].title,
                           'publishedAt':vods[0].upload_date}
        record['sourceCheck']={
            'status':'vod_found' if vods else 'not_found',
            'message': f'공개 VOD {len(vods)}개 발견 · 24초 간격 고속 탐색 · 발로란트 화면만 세부 분석'
                       if vods else '재생 가능한 공개 라이브 다시보기를 찾지 못했습니다.'}
        for video in vods:
            key=player+'|'+video.url
            if not should_scan(state.get(key),now,force):
                continue
            if catalog is None:
                try:
                    catalog=catalog_getter()
                except Exception:
                    events.append({'player':player,'url':video.url,'status':'error',
                                   'scanned_at':now_stamp,
                                   'errors':['무료 스킨 목록을 가져올 수 없습니다.']})
                    break
            if icon_matcher is None and icon_warning is None:
                try:
                    icon_matcher=ImageSkinMatcher(load_api_catalog())
                except Exception:
                    icon_warning='이미지 비교 참조 목록을 읽지 못했습니다.'
            result=scan_video(video,catalog,vision_matcher=icon_matcher)
            if icon_warning:
                result['vision_warning']=icon_warning
            events.append(result)
            state[key]={'scanned_at':now_stamp,'status':result['status'],
                        'revision':REVISION}
            if result['status']=='verified':
                for candidate in result['candidates']:
                    if candidate.get('hits',0)<2:
                        continue
                    record['weapons'][candidate['weapon']]={
                        'skin':candidate['skin'],
                        'verified':True,
                        'source':video.url,
                        'timestamp_seconds':candidate['timestamp_seconds'],
                        'checkedAt':now_stamp,
                        'method':candidate.get('method','ocr_full_name')+'_two_frames',
                        'image':candidate.get('image'),
                        'score':candidate.get('score')}
                    record['checkedAt']=now_stamp
                record['sourceCheck']={
                    'status':'verified',
                    'message':'발로란트 영상에서 컬렉션 스킨을 2개 프레임으로 검증했습니다.'}
            elif record['sourceCheck']['status']!='verified':
                labels={
                    'no_valorant':'표본 화면에서 발로란트 플레이를 찾지 못해 다른 게임 구간을 건너뛰었습니다.',
                    'valorant_no_collection':'발로란트 플레이 확인 · 컬렉션 화면은 찾지 못했습니다.',
                    'collection_no_text_or_image':'컬렉션 확인 · 스킨 이미지/이름 미확인',
                    'candidate_found':'스킨 후보 발견 · 프레임 2개 확인 실패',
                    'error':'공개 다시보기 접근 또는 영상 해석 실패'
                }
                record['sourceCheck']={
                    'status':result['status'],
                    'message': labels.get(result['status'],'고속 분석 상태 확인 중')}
    # Publish only AFTER the single-player scan completes, so the website
    # never sees a partially processed VOD or unverified loadout.
    finished=datetime.now(timezone.utc).isoformat()
    for player,(vods,_) in discovery.items():
        record=latest['players'][player]
        own_events=[item for item in events if item.get('player')==player]
        status=(own_events[-1]['status'] if own_events
                else 'no_new_vod' if vods else 'no_public_vod')
        record['lastScanFinishedAt']=finished
        record['lastAutomaticRun']={
            'status':status,
            'finishedAt':finished,
            'videosFound':len(vods),
            'videosExamined':len(own_events),
        }
        if not own_events and vods:
            record['sourceCheck']={
                'status':'already_checked',
                'message':'새로운 공개 다시보기 없음 · 이전 검증 결과 유지'
            }
    latest['lastAutomaticPublishAt']=finished
    write_json('latest.json',latest)
    write_json('scan_state.json',state)
    write_json('history.json',(events+history)[:80])
    print(json.dumps({
        'discovered':{p:len(v) for p,(v,_) in discovery.items()},
        'scanned':len(events),
        'verified':sum(e.get('status')=='verified' for e in events),
        'skipped_other_games':sum(e.get('skipped_non_valorant_segments',0) for e in events),
        'sampled_frames':sum(e.get('frames_sampled',0) for e in events)
    },ensure_ascii=False))

if __name__=='__main__':
    run()
