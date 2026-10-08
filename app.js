'use strict';


const weapons = ['Classic','Shorty','Frenzy','Ghost','Sheriff','Stinger','Spectre','Bucky','Judge','Bulldog','Guardian','Phantom','Vandal','Marshal','Outlaw','Operator','Ares','Odin','Melee'];
const $ = id => document.getElementById(id);
let snapshot = null;
let requestId = 0;
function safeVideoUrl(value) {
  try { const u = new URL(value); return u.protocol === 'https:' && ['youtube.com','www.youtube.com','m.youtube.com','youtu.be','twitch.tv','www.twitch.tv'].includes(u.hostname) && !u.username && !u.password ? u : null; } catch { return null; }
}
function render() {
  const result = snapshot?.players?.[$('player').value];
  $('vod-status').textContent = result?.analysis?.message || '';
  const query = $('search').value.trim().toLowerCase();
  const verified = weapons.filter(w => result?.weapons?.[w]?.verified === true && typeof result.weapons[w].skin === 'string' && result.weapons[w].skin.trim());
  $('verified-count').textContent = `확인 ${verified.length}개`;
  const date = result?.checkedAt ? new Date(result.checkedAt) : null;
  $('checked-at').textContent = date && !Number.isNaN(date.getTime()) ? `결과 확인 시각: ${date.toLocaleString('ko-KR')}` : '실제 확인 기록 없음';
  $('weapon-grid').replaceChildren();
  for (const w of weapons.filter(w => w.toLowerCase().includes(query))) {
    const card = document.createElement('article'); card.className = 'weapon';
    const title = document.createElement('h3'); title.textContent = w;
    const skin = document.createElement('p'); const confirmed = verified.includes(w);
    skin.className = confirmed ? 'confirmed' : 'unknown'; skin.textContent = confirmed ? result.weapons[w].skin : '미확인';
    const note = document.createElement('small'); note.textContent = confirmed ? (result.weapons[w].verificationMethod?.startsWith('ai-') ? `AI 확인 · ${new Date(result.weapons[w].observedAt).toLocaleString('ko-KR')}` : '확인된 기록') : '확인 결과가 아직 없습니다';
    card.append(title, skin, note); $('weapon-grid').append(card);
  }
  if (!$('weapon-grid').children.length) $('weapon-grid').textContent = '검색 결과가 없습니다.';
  $('source').replaceChildren();
  const url = safeVideoUrl(result?.vod?.url);
  if (url) { const a = document.createElement('a'); a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.textContent = `${result?.analysis?.status === 'source_unavailable' ? '분석 대상: ' : ''}${result.vod.title || '출처 영상'}`; $('source').append(a); }
  else $('source').textContent = '등록된 출처 영상 없음';
}
async function refresh() {
  const id = ++requestId; $('refresh').disabled = true; $('status').textContent = '저장된 결과를 불러오는 중…';
  try {
    const response = await fetch(`${server ? server+'/api/latest' : 'latest.json'}?t=${Date.now()}`, {cache:'no-store', signal:AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error('load');
    const data = await response.json();
    if (data.schemaVersion !== 1 || !data.players || typeof data.players !== 'object' || Array.isArray(data.players)) throw new Error('format');
    if (id !== requestId) return;
    snapshot = data; render(); if (!polling) $('status').textContent = server ? '분석 서버의 확인 결과를 불러왔습니다.' : '저장된 결과를 읽었습니다. 자동 분석을 사용하려면 서버를 연결하세요.';
  } catch {
    if (id !== requestId) return;
    $('status').textContent = '결과를 불러오지 못했습니다. 기존 표시를 유지합니다. 로컬 서버 또는 배포 주소에서 다시 시도하세요.';
  } finally { if (id === requestId) $('refresh').disabled = false; }
}
$('player').addEventListener('change',render);
$('search').addEventListener('input',render);
$('refresh').addEventListener('click',()=>server ? startScan(true) : refresh());
$('vod-form').addEventListener('submit',event => {
  event.preventDefault(); const url = safeVideoUrl($('vod-url').value.trim());
  if (!url) { $('vod-status').textContent = 'YouTube 또는 Twitch의 HTTPS 영상 주소를 입력하세요.'; return; }
  if (server) { startScan(true,url.href); return; }
  window.open(url.href,'_blank','noopener,noreferrer');
  $('vod-status').textContent = '영상 열기를 요청했습니다. 이 단계에서는 영상 분석이나 스킨 확인 기록을 저장하지 않습니다.';
});
let server = '';
let token = '';
let polling = false;
let pollTimer = null;
try { server = localStorage.getItem('val-live-server') || ''; token = sessionStorage.getItem('val-live-token') || ''; } catch {}
function validServer(value) {
  try { const u=new URL(value); return !u.username && !u.password && (u.protocol==='https:' || (u.protocol==='http:' && ['localhost','127.0.0.1'].includes(u.hostname))) && u.pathname==='/' && !u.search && !u.hash ? u.origin : ''; } catch { return ''; }
}
server=validServer(server);
async function api(path,body) {
  const r=await fetch(server+path,{method:body ? 'POST':'GET',headers:body ? {'Content-Type':'application/json','Authorization':'Bearer '+token}:{},body:body ? JSON.stringify(body):undefined,signal:AbortSignal.timeout(20000),cache:'no-store'});
  const j=await r.json(); if(!r.ok) throw new Error(j.error || '서버 요청 실패'); return j;
}
async function poll() {
  try {
    const s=await api('/api/status');
    $('status').textContent=s.message+(s.status==='running' ? ' · '+s.frames+'개 화면 확인':'');
    if(s.status==='running') { pollTimer=setTimeout(poll,3000); return; }
    polling=false; $('cancel-scan').hidden=true; await refresh(); $('status').textContent=s.message;
  } catch(e) { polling=false; $('cancel-scan').hidden=true; $('status').textContent='상태 조회 실패: '+e.message+' 서버 작업은 계속 실행 중일 수 있습니다.'; }
}
async function startScan(force=false,url='') {
  if(!server || !token) { $('status').textContent='분석 서버 주소와 암호를 먼저 입력하세요.'; return; }
  if(polling) return;
  polling=true; $('refresh').disabled=true;
  try {
    const s=await api('/api/analyze',{player:$('player').value,url,force});
    if(s.status==='cached') { polling=false; await refresh(); $('status').textContent=s.message; return; }
    $('cancel-scan').hidden=false; await poll();
  } catch(e) { polling=false; $('status').textContent=e.message; }
  finally { $('refresh').disabled=false; }
}
$('server-url').value=server;
$('connect-form').addEventListener('submit',async e=>{
  e.preventDefault(); const next=validServer($('server-url').value.trim());
  if(!next) { $('status').textContent='HTTPS 서버 기본 주소를 입력하세요.'; return; }
  server=next; token=$('scan-token').value; $('scan-token').value='';
  try { localStorage.setItem('val-live-server',server); sessionStorage.setItem('val-live-token',token); } catch {}
  try { const h=await api('/api/health'); if(!h.ready) throw new Error('서버에 API 키와 분석 암호 설정이 필요합니다.'); await refresh(); await startScan(); }
  catch(e) { $('status').textContent=e.message; }
});
$('cancel-scan').addEventListener('click',async()=>{
  try { await api('/api/cancel',{}); $('status').textContent='중지 요청을 보냈습니다.'; } catch(e) { $('status').textContent=e.message; }
});

render(); refresh().then(()=>{if(server && token)startScan();});
