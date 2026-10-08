'use strict';

/* VAL-LIVE reads completed results only.
   Video searches and image scanning run automatically on the scheduled server
   workflow, ONE player at a time. No user GitHub access or credentials required. */
const WEAPONS=[
  'Classic','Shorty','Frenzy','Ghost','Sheriff','Stinger','Spectre','Bucky',
  'Judge','Bulldog','Guardian','Phantom','Vandal','Marshal','Outlaw',
  'Operator','Ares','Odin','Melee'
];
const PLAYERS=['TenZ','aspas','t3xture','something'];
const SCAN_UTC_HOUR=Object.freeze({TenZ:0,aspas:6,t3xture:12,something:18});
const $=id=>document.getElementById(id);
let data=null;
let historyLog=[];
let snapshot='';
let loading=false;

function safeUrl(value, icon=false){
  try{
    const u=new URL(String(value||''));
    if(u.protocol!=='https:')return null;
    const hosts=icon?['media.valorant-api.com']:
      ['youtube.com','www.youtube.com','youtu.be','twitch.tv','www.twitch.tv'];
    return hosts.includes(u.hostname)?u.href:null;
  }catch{return null}
}
function formatDate(value){
  if(!value)return '기록 없음';
  const d=new Date(value);
  if(Number.isNaN(d.getTime()))return '기록 없음';
  return d.toLocaleString('ko-KR',{
    timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',
    hour:'2-digit',minute:'2-digit',hour12:false
  });
}
function link(url,title){
  const a=document.createElement('a');
  a.href=url;
  a.target='_blank';
  a.rel='noopener noreferrer';
  a.textContent=title;
  return a;
}
function activePlayer(){
  const value=$('player').value;
  return PLAYERS.includes(value)?value:'TenZ';
}
function nextScheduledRun(player){
  const n=new Date();
  const hour=SCAN_UTC_HOUR[player];
  const next=new Date(Date.UTC(n.getUTCFullYear(),n.getUTCMonth(),n.getUTCDate(),hour,37));
  if(next<=n)next.setUTCDate(next.getUTCDate()+1);
  return next;
}
function textElement(className,value){
  const p=document.createElement('p');
  p.className=className;
  p.textContent=value;
  return p;
}
function skinCards(record){
  const grid=$('weapon-grid');
  grid.replaceChildren();
  const q=$('search').value.trim().toLowerCase();
  const equipped=record.weapons||{};
  let confirmed=0;
  for(const weapon of WEAPONS){
    const entry=equipped[weapon];
    if(entry?.verified===true&&typeof entry.skin==='string'&&entry.skin.trim())confirmed++;
    if(!weapon.toLowerCase().includes(q))continue;
    const card=document.createElement('article');
    card.className='weapon';
    const title=document.createElement('h3');
    title.textContent=weapon;
    const valid=entry?.verified===true&&typeof entry.skin==='string'&&!!entry.skin.trim();
    const skinName=document.createElement('p');
    skinName.className=valid?'confirmed':'unknown';
    skinName.textContent=valid?entry.skin:'미확인';
    const tag=document.createElement('small');
    tag.textContent=valid?'방송에서 두 프레임 확인':'확인된 스킨 없음';
    card.append(title,skinName,tag);
    if(valid){
      const icon=safeUrl(entry.image,true);
      if(icon){
        const image=document.createElement('img');
        image.className='skin-preview';
        image.src=icon;image.alt=entry.skin+' 아이콘';image.loading='lazy';
        image.referrerPolicy='no-referrer';
        card.append(image);
      }
      if(typeof entry.method==='string'&&entry.method.includes('image_template_match')){
        const method=document.createElement('small');
        method.className='method-tag';
        method.textContent='컬렉션 이미지 대조';
        card.append(method);
      }
      const source=safeUrl(entry.source||entry.sourceUrl);
      if(source)card.append(link(source,' · 근거 영상 ↗'));
    }
    grid.append(card);
  }
  $('verified-count').textContent='확인 '+confirmed+'개';
}
function videoCards(record){
  const area=$('vod-list');
  area.replaceChildren();
  const vods=Array.isArray(record.discoveredVods)?record.discoveredVods:[];
  let found=0;
  for(const item of vods){
    const url=safeUrl(item.url);
    if(!url)continue;
    const row=document.createElement('article');
    row.className='vod-item';
    row.append(link(url,'▶ '+(item.title||'라이브 다시보기')));
    const meta=document.createElement('small');
    meta.textContent=(item.platform||'공개 영상')+' · 자동 검색';
    row.append(meta);
    area.append(row);
    found++;
  }
  if(!found)area.append(textElement('muted','공개 다시보기를 찾지 못했거나 영상 접근이 제한되었습니다.'));
  const source=$('source');
  source.replaceChildren();
  for(const item of (record.channels||[])){
    const url=safeUrl(item.url);
    if(url)source.append(link(url,(item.label||'채널')+' ↗'));
  }
}
function historyCards(player){
  const area=$('history');
  area.replaceChildren();
  const label={
    verified:'스킨 확인 완료',candidate_found:'스킨 후보 확인 · 미확정',
    valorant_no_collection:'발로란트 확인 · 컬렉션 미발견',
    collection_no_text_or_image:'컬렉션 발견 · 스킨 미확인',
    no_valorant:'발로란트 화면 미발견',no_collection:'컬렉션 화면 미발견',
    error:'영상 접근 또는 분석 실패'
  };
  const items=historyLog.filter(item=>item.player===player).slice(0,8);
  if(!items.length){
    area.append(textElement('muted','아직 이 선수의 분석 기록이 없습니다.'));
    return;
  }
  for(const item of items){
    const row=document.createElement('p');
    const result=label[item.status]||'자동 확인 시도';
    const names=(item.candidates||[]).map(c=>c.skin).filter(Boolean).slice(0,5);
    row.textContent=result+' · '+formatDate(item.scanned_at)+
       (names.length?' · '+names.join(', '):'');
    const source=safeUrl(item.url);
    if(source)row.append(' ',link(source,'영상 ↗'));
    area.append(row);
  }
}
function render(){
  const player=activePlayer();
  const record=data?.players?.[player]||{};
  $('checked-at').textContent=record.checkedAt
    ?'마지막으로 스킨을 검증한 시각: '+formatDate(record.checkedAt)
    :'검증 완료한 스킨 기록 없음';
  const detected=record.sourceCheck?.message||
    '해당 선수의 첫 자동 분석 결과를 기다리는 중입니다.';
  const checked=record.lastScanFinishedAt||record.discoveredAt;
  $('analysis').textContent=detected+
    (checked?' · 최근 자동 검색: '+formatDate(checked):'');
  const next=nextScheduledRun(player);
  $('next-check').textContent=player+' 다음 자동 확인 예정: '+
    formatDate(next.toISOString())+' (한국시간, 실행이 지연될 수 있음)';
  skinCards(record);
  videoCards(record);
  historyCards(player);
}
async function readJSON(filename){
  const response=await fetch(filename+'?cache='+Date.now(),{cache:'no-store'});
  if(!response.ok)throw new Error(filename+' HTTP '+response.status);
  return response.json();
}
async function refresh({automatic=false}={}){
  if(loading)return;
  loading=true;
  const button=$('refresh');
  button.disabled=true;
  try{
    const fresh=await readJSON('latest.json');
    if(fresh.schemaVersion!==1||!fresh.players||typeof fresh.players!=='object'){
      throw new Error('최신 데이터 형식 오류');
    }
    let newHistory=[];
    try{
      const h=await readJSON('history.json');
      if(Array.isArray(h))newHistory=h;
    }catch{
      newHistory=historyLog;
    }
    const nextSnapshot=JSON.stringify({players:fresh.players,history:newHistory});
    const changed=!!snapshot&&snapshot!==nextSnapshot;
    data=fresh;historyLog=newHistory;snapshot=nextSnapshot;
    render();
    const minute=new Date().toLocaleTimeString('ko-KR',
      {timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit'});
    $('status').textContent=changed
      ?'새로운 자동 검색/스킨 확인 결과를 사이트에 반영했습니다. ('+minute+')'
      :automatic
        ?'자동 동기화 중 · 최근 확인 '+minute
        :'저장된 최신 결과 확인 완료 · '+minute;
  }catch(error){
    $('status').textContent='데이터 갱신에 실패했습니다: '+error.message+
      ' · 기존 화면은 유지됩니다.';
  }finally{
    loading=false;
    button.disabled=false;
  }
}
$('player').addEventListener('change',()=>{
  render();
  $('status').textContent=activePlayer()+'의 마지막 자동 확인 결과를 보고 있습니다.';
});
$('search').addEventListener('input',render);
$('refresh').addEventListener('click',()=>{void refresh()});
$('run-scan').addEventListener('click',()=>{
  const player=activePlayer();
  $('status').textContent=player+' 즉시 분석: GitHub 로그인 후 Run workflow → 선수 선택 → Run workflow를 누르세요. 분석 완료 후 결과는 자동 갱신됩니다.';
  window.open('https://github.com/K3ANER/val-live/actions/workflows/scan.yml','_blank','noopener,noreferrer');
});
document.addEventListener('visibilitychange',()=>{
  if(!document.hidden)void refresh({automatic:true});
});
window.addEventListener('online',()=>{void refresh({automatic:true})});
setInterval(()=>{
  if(!document.hidden&&navigator.onLine!==false)void refresh({automatic:true});
},60_000);
void refresh();
