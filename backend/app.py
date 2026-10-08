import hmac
import json
import os
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from flask import Flask, request, jsonify, send_file
from .config import DATA_DIR, PLAYERS
from .scan import scan, resolve_source, validate_url

app=Flask(__name__)
ROOT=Path(__file__).resolve().parent.parent
DATA_DIR.mkdir(parents=True,exist_ok=True)
FILE=DATA_DIR/'latest.json'
lock=threading.RLock()
stop=threading.Event()
state={'status':'idle','player':None,'frames':0,'message':'대기 중'}
last_start=0.0
last_success={}

def now(): return datetime.now(timezone.utc).isoformat()
def ready(): return bool(os.getenv('OPENAI_API_KEY') and os.getenv('SCAN_TOKEN') and shutil.which('ffmpeg'))
def read_data():
    if FILE.exists(): return json.loads(FILE.read_text())
    initial=ROOT/'latest.json'
    if initial.exists(): return json.loads(initial.read_text())
    return {'schemaVersion':1,'players':{p:{'checkedAt':None,'vod':None,'weapons':{}} for p in PLAYERS}}
def save_data(data):
    temp=FILE.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(FILE)
def update_state(**kwargs):
    with lock: state.update(kwargs)
def publish_github(data):
    token=os.getenv('GITHUB_TOKEN')
    if not token: return False
    endpoint='https://api.github.com/repos/K3ANER/val-live/contents/latest.json'
    headers={'Authorization':f'Bearer {token}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    r=requests.get(endpoint,headers=headers,timeout=20);r.raise_for_status()
    import base64
    payload={'message':'Update verified collection scan','sha':r.json()['sha'],'branch':'main',
             'content':base64.b64encode(json.dumps(data,ensure_ascii=False,indent=2).encode()).decode()}
    response=requests.put(endpoint,headers=headers,json=payload,timeout=20)
    response.raise_for_status();return True

def worker(player,url):
    try:
        update_state(message='라이브 / 최신 다시보기 찾는 중')
        source=resolve_source(PLAYERS[player],url)
        def progress(count,offset,message): update_state(frames=count,offsetSeconds=offset,message=message)
        result=scan(source,progress,stop)
        if stop.is_set(): result={'status':'cancelled','weapons':{}}
        messages={'completed':'컬렉션 식별 완료 · 영상 확인 종료',
                  'collection_unverified':'컬렉션 발견 · 스킨 확정 불가 · 영상 확인 종료',
                  'not_found':'스캔 범위에서 컬렉션을 찾지 못했습니다.',
                  'timeout':'확인 시간 제한에 도달했습니다.', 'cancelled':'영상 확인을 중지했습니다.'}
        data=read_data(); current=data['players'].setdefault(player,{'weapons':{}})
        current['analysis']={k:v for k,v in result.items() if k!='weapons'}
        current['analysis'].update(message=messages[result['status']],attemptedAt=now())
        # Keep the old source/date if no new verified result, so old skins aren't attributed to a new video.
        current['analysis']['source']={k:source[k] for k in ('url','title','publishedAt','live')}
        if result['status']=='completed':
            stamp=now()
            for weapon,value in result['weapons'].items():
                current.setdefault('weapons',{})[weapon]={**value,'observedAt':stamp,'sourceUrl':source['url']}
            current['checkedAt']=stamp
            current['vod']={k:source[k] for k in ('url','title','publishedAt','live')}
            last_success[player]=time.monotonic()
        with lock: save_data(data)
        message=messages[result['status']]
        if result['status']=='completed':
            try:
                if publish_github(data): message+=' · GitHub 결과 반영 완료'
            except Exception: message+=' · 서버 결과 저장 완료, GitHub 반영 실패'
        update_state(status=result['status'],message=message,finishedAt=now())
    except Exception:
        # Never expose yt-dlp signed URLs, API keys, or provider response bodies to a public client.
        update_state(status='failed',message='영상 접근 또는 비전 분석에 실패했습니다. 서버 설정·로그를 확인하세요.',finishedAt=now())

@app.after_request
def cors(response):
    origin=request.headers.get('Origin','')
    allowed={x.strip() for x in os.getenv('ALLOWED_ORIGINS','https://k3aner.github.io').split(',')}
    if origin in allowed:
        response.headers['Access-Control-Allow-Origin']=origin
        response.headers['Vary']='Origin'
        response.headers['Access-Control-Allow-Headers']='Authorization, Content-Type'
        response.headers['Access-Control-Allow-Methods']='GET, POST, OPTIONS'
    response.headers['Cache-Control']='no-store'
    return response

def authorized():
    expected=os.getenv('SCAN_TOKEN','')
    return bool(expected) and hmac.compare_digest(request.headers.get('Authorization',''), 'Bearer '+expected)

@app.get('/api/health')
def health(): return jsonify(ready=ready())
@app.get('/api/latest')
def latest():
    with lock: return jsonify(read_data())
@app.get('/api/status')
def status():
    with lock: return jsonify(dict(state))
@app.route('/api/analyze',methods=['POST','OPTIONS'])
def analyze():
    global last_start
    if request.method=='OPTIONS': return '',204
    if not authorized(): return jsonify(error='서버의 SCAN_TOKEN과 일치하는 분석 암호가 필요합니다.'),401
    if not ready(): return jsonify(error='OPENAI_API_KEY, SCAN_TOKEN, FFmpeg 설정을 완료하세요.'),503
    body=request.get_json(silent=True) or {}
    player=body.get('player','TenZ');url=body.get('url') or None
    if player not in PLAYERS: return jsonify(error='지원하지 않는 선수입니다.'),400
    try:
        if url: validate_url(url)
    except Exception: return jsonify(error='YouTube/Twitch HTTPS 주소를 확인하세요.'),400
    with lock:
        if state['status']=='running': return jsonify(dict(state)),202
        if not body.get('force') and not url and time.monotonic()-last_success.get(player,-99999)<1800:
            return jsonify(status='cached',message='최근 확인 결과를 표시합니다.'),200
        if time.monotonic()-last_start<60: return jsonify(error='1분 뒤 다시 시도하세요.'),429
        last_start=time.monotonic();stop.clear()
        state.clear();state.update(status='running',player=player,frames=0,message='분석 시작',startedAt=now())
        threading.Thread(target=worker,args=(player,url),daemon=True).start()
        return jsonify(dict(state)),202
@app.route('/api/cancel',methods=['POST','OPTIONS'])
def cancel():
    if request.method=='OPTIONS': return '',204
    if not authorized(): return jsonify(error='분석 암호가 필요합니다.'),401
    stop.set(); return jsonify(ok=True,message='중지 요청됨')
@app.get('/')
def home(): return send_file(ROOT/'index.html')
@app.get('/<name>')
def asset(name):
    if name not in {'app.js','styles.css','latest.json'}: return '',404
    if name=='latest.json': return latest()
    return send_file(ROOT/name)
