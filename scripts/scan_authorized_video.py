#!/usr/bin/env python3
"""VAL LIVE: analyze an authorized local video, never guess unobserved skins."""
import argparse, base64, datetime, json, os, pathlib, re, subprocess, tempfile, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
WEAPONS=['Classic','Shorty','Frenzy','Ghost','Sheriff','Stinger','Spectre','Bucky','Judge','Bulldog','Guardian','Phantom','Vandal','Marshal','Outlaw','Operator','Ares','Odin','Melee']
def frame(video,second,path):
    return subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-ss',str(second),'-i',str(video),'-frames:v','1','-vf','scale=1280:-2', '-y',str(path)],capture_output=True).returncode==0 and path.exists()
def duration(video):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(video)],capture_output=True,text=True,check=True)
    return float(p.stdout.strip())
def ask(image,key):
    payload={'model':os.environ.get('VISION_MODEL','gpt-4.1-mini'),'temperature':0,'max_tokens':550,'messages':[{'role':'system','content':'Inspect a VALORANT screenshot. Return ONLY JSON {"collection": boolean, "skins": {"Vandal": "exact skin name"}, "confidence": number}. collection true ONLY if an actual weapon collection/loadout screen is clearly visible, not gameplay or shop. Report a skin only if the weapon and equipped skin name are unambiguously legible. No guesses. Confidence 0-1. Empty skins when uncertain.'},{'role':'user','content':[{'type':'text','text':'Is this the VALORANT collection/loadout screen? Identify ONLY clearly readable equipped weapon skins.'},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(image.read_bytes()).decode()}}]}]}
    req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as r: text=json.load(r)['choices'][0]['message']['content']
    return json.loads(re.sub(r'^\x60{3}(?:json)?|\x60{3}$','',text.strip()).strip())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--video',required=True,help='Local video file you have permission to analyze');ap.add_argument('--player',choices=['TenZ','aspas','t3xture','something'],required=True);ap.add_argument('--source',default='');ap.add_argument('--interval',type=int,default=20);a=ap.parse_args()
    key=os.getenv('OPENAI_API_KEY')
    if not key: raise SystemExit('OPENAI_API_KEY is required')
    d=duration(a.video);path=ROOT/'latest.json';db=json.loads(path.read_text());found={};hits=0
    with tempfile.TemporaryDirectory() as tmp:
        image=pathlib.Path(tmp)/'frame.jpg'
        for second in range(0,int(d)+1,max(5,a.interval)):
            if not frame(a.video,second,image): continue
            try: result=ask(image,key)
            except Exception as e: print('Frame error:',str(e)[:160]);continue
            if result.get('collection') is not True or float(result.get('confidence',0))<0.9: continue
            hits+=1
            for w,skin in result.get('skins',{}).items():
                if w in WEAPONS and isinstance(skin,str) and len(skin.strip())>=4: found[w]={'skin':skin.strip(),'verified':True,'verificationMethod':'ai-vision-provisional','observedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'videoSecond':second,'sourceUrl':a.source}
            if found: break  # stop at first collection screen with readable skins
    p=db['players'][a.player];p.setdefault('weapons',{}).update(found)
    p['analysis']={'status':'ai_candidate_needs_review' if found else 'collection_not_verified','framesScanned':'until_first_verified_collection' if found else 'entire_video','message':'AI-generated candidate labels, not independently verified' if found else 'No legible collection skins found'}
    if found: p['checkedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    path.write_text(json.dumps(db,ensure_ascii=False,indent=2)+'\n')
    print('Collection frames:',hits,'candidate skins:',len(found))
if __name__=='__main__': main()
