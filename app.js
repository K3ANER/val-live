'use strict';
const weapons=['Classic','Shorty','Frenzy','Ghost','Sheriff','Stinger','Spectre','Bucky','Judge','Bulldog','Guardian','Phantom','Vandal','Marshal','Outlaw','Operator','Ares','Odin','Melee'];
const $=id=>document.getElementById(id);
let data=null, history=[], config={workerUrl:''}, monitor=null;
const safeURL=s=>{try{const u=new URL(String(s));return u.protocol==='https:'&&['www.youtube.com','youtube.com','youtu.be','www.twitch.tv','twitch.tv'].includes(u.hostname)?u.href:null}catch{return null}};
const time=s=>{try{return new Date(s).toLocaleString('ko-KR')}catch{return '-'}};
function anchor(url,title){const link=document.createElement('a');link.href=url;link.rel='noopener noreferrer';link.target='_blank';link.textContent=title;return link}
function render(){
  const player=$('player').value,r=data?.players?.[player]||{},q=$('search').value.toLowerCase();
  const count=weapons.filter(w=>r.weapons?.[w]?.verified===true&&r.weapons[w].skin).length;
  $('verified-count').textContent='확인 '+count+'개';
  $('checked-at').textContent=r.checkedAt?'마지막 스킨 확인: '+time(r.checkedAt):'검증된 스킨 기록 없음';
  $('weapon-grid').replaceChildren();
  for(const w of weapons.filter(w=>w.toLowerCase().includes(q))){
    const e=r.weapons?.[w], ok=e?.verified===true&&typeof e.skin==='string'&&e.skin.trim();
    const card=document.createElement('article');card.className='weapon';
    const h=document.createElement('h3');h.textContent=w;
    const p=document.createElement('p');p.className=ok?'confirmed':'unknown';p.textContent=ok?e.skin:'미확인';
    const small=document.createElement('small');small.textContent=ok?'영상에서 확인된 스킨':'검증된 스킨 없음';
    const imgURL=e?.image;
    if(ok&&typeof imgURL==='string'){
      try{const u=new URL(imgURL);if(u.protocol==='https:'&&u.hostname==='media.valorant-api.com'){
        const img=document.createElement('img');img.src=u.href;img.alt=e.skin+' 스킨 이미지';
        img.loading='lazy';img.referrerPolicy='no-referrer';img.className='skin-preview';card.append(img);
      }}catch{}
    }
    if(ok&&e.method?.startsWith('image_template_match')){
      const tag=document.createElement('small');tag.className='method-tag';tag.textContent='이미지 비교 · 컬렉션 2프레임 확인';card.append(tag);
    }
    card.append(h,p,small);
    const url=safeURL(e?.source);if(ok&&url)card.append(anchor(url,' · 근거 영상 ↗'));
    $('weapon-grid').append(card);
  }
  $('analysis').textContent=r.sourceCheck?.message||'자동 영상 탐색 전';
  $('vod-list').replaceChildren();
  const vods=Array.isArray(r.discoveredVods)?r.discoveredVods:[];
  if(!vods.length){const p=document.createElement('p');p.className='muted';p.textContent='찾은 공개 다시보기 없음 (분석 준비 또는 공개 영상 없음)';$('vod-list').append(p)}
  for(const v of vods){const u=safeURL(v.url);if(!u)continue;const article=document.createElement('article');article.className='vod-item';
    article.append(anchor(u,'▶ '+(v.title||'라이브 다시보기')));
    const info=document.createElement('small');info.textContent=' '+(v.platform||'')+' · 자동 검색';article.append(info);$('vod-list').append(article)}
  $('source').replaceChildren();
  for(const c of r.channels||[]){const u=safeURL(c.url);if(u){$('source').append(anchor(u,(c.label||'채널')+' ↗'));}}
  const recent=history.filter(x=>x.player===player).slice(0,8);$('history').replaceChildren();
  if(!recent.length){const p=document.createElement('p');p.className='muted';p.textContent='선택 선수의 분석 기록 없음';$('history').append(p)}
  for(const item of recent){const row=document.createElement('p');let label=item.status==='verified'?'스킨 확인':item.status==='candidate_found'?'스킨 후보 (미확정)':['collection_no_text','collection_no_text_or_image'].includes(item.status)?'컬렉션 탐색 · 이미지/텍스트 미확인':item.status==='no_valorant'?'발로란트 화면 미발견 · 다른 게임 구간 건너뜀':item.status==='valorant_no_collection'?'발로란트 감지 · 컬렉션 없음':item.status==='error'?'접근/분석 오류':'컬렉션 장면 미발견';
    row.textContent=label+' · '+time(item.scanned_at)+(item.analysis_mode==='fast_valorant_only'?' · 24초 빠른 탐색 / 4초 세부 검사':'')+' · '+((item.candidates||[]).map(c=>c.skin+(c.method==='image_template_match'?' [이미지]':'')).join(', ')||'확인 항목 없음');
    const url=safeURL(item.url);if(url)row.append(' ',anchor(url,'영상 ↗'));
    $('history').append(row)}
}
async function fetchJSON(file){const r=await fetch(file+'?v='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error(file+' HTTP '+r.status);return r.json()}
async function loadData(){try{const j=await fetchJSON('latest.json');if(j.schemaVersion!==1||!j.players)throw Error('최신 데이터 형식 오류');data=j}catch(e){$('status').textContent='스킨 데이터 불러오기 실패: '+e.message}
  try{const j=await fetchJSON('history.json');history=Array.isArray(j)?j:[]}catch{history=[]}render()}
async function loadConfig(){try{const j=await fetchJSON('config.json');const u=new URL(j.workerUrl);if(u.protocol==='https:')config.workerUrl=u.href}catch{};
  $('refresh').textContent=config.workerUrl?'↻ 전체 최신화 시작':'↻ 저장된 결과 새로고침';
  $('setup').textContent=config.workerUrl?'최신화 서버 주소가 등록되었습니다. 버튼만 누르세요.':'원클릭 실행 서버가 아직 연결되지 않았습니다. GitHub Actions는 예약 실행되며 이 버튼은 현재 결과를 다시 불러옵니다.'}
async function refresh(){const b=$('refresh');b.disabled=true;
  if(config.workerUrl){$('status').textContent='공개 다시보기 자동 검색을 서버에 요청하는 중…';
    try{const res=await fetch(config.workerUrl,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      const payload=await res.json().catch(()=>({}));if(!res.ok)throw Error(payload.error||`HTTP ${res.status}`);
      $('status').textContent='스캔 요청 완료 · 선수별 최신 다시보기를 자동 탐색 중… 완료되면 이 화면이 자동 갱신됩니다.';
      if(monitor)clearInterval(monitor);
      const start=Date.now(), initial=JSON.stringify(Object.fromEntries(Object.entries(data?.players||{}).map(([n,v])=>[n,v.discoveredAt||''])));
      monitor=setInterval(async()=>{
        if(Date.now()-start>20*60*1000){clearInterval(monitor);monitor=null;return}
        await loadData();
        const current=JSON.stringify(Object.fromEntries(Object.entries(data?.players||{}).map(([n,v])=>[n,v.discoveredAt||''])));
        if(current!==initial){clearInterval(monitor);monitor=null;$('status').textContent='자동 영상 검색/분석의 새 결과를 불러왔습니다.'}
      },20000);
    }catch(e){$('status').textContent='분석 요청 실패: '+e.message}}
  else{$('status').textContent='서버 최초 설정 전: 저장된 최근 검색 결과만 새로 불러옵니다.'}
  await loadData();b.disabled=false;
}
$('player').addEventListener('change',render);
$('search').addEventListener('input',render);
$('refresh').addEventListener('click',refresh);
loadConfig().then(loadData);