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
    const note = document.createElement('small'); note.textContent = confirmed ? '확인된 기록' : '확인 결과가 아직 없습니다';
    card.append(title, skin, note); $('weapon-grid').append(card);
  }
  if (!$('weapon-grid').children.length) $('weapon-grid').textContent = '검색 결과가 없습니다.';
  $('source').replaceChildren();
  const url = safeVideoUrl(result?.vod?.url);
  if (url) { const a = document.createElement('a'); a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.textContent = result.vod.title || '확인에 사용한 영상'; $('source').append(a); }
  else $('source').textContent = '등록된 출처 영상 없음';
}
async function refresh() {
  const id = ++requestId; $('refresh').disabled = true; $('status').textContent = '저장된 결과를 불러오는 중…';
  try {
    const response = await fetch(`latest.json?t=${Date.now()}`, {cache:'no-store', signal:AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error('load');
    const data = await response.json();
    if (data.schemaVersion !== 1 || !data.players || typeof data.players !== 'object' || Array.isArray(data.players)) throw new Error('format');
    if (id !== requestId) return;
    snapshot = data; render(); $('status').textContent = '저장된 결과를 다시 읽었습니다. 자동 영상 분석은 미연결 상태입니다.';
  } catch {
    if (id !== requestId) return;
    $('status').textContent = '결과를 불러오지 못했습니다. 기존 표시를 유지합니다. 로컬 서버 또는 배포 주소에서 다시 시도하세요.';
  } finally { if (id === requestId) $('refresh').disabled = false; }
}
$('player').addEventListener('change',render);
$('search').addEventListener('input',render);
$('refresh').addEventListener('click',refresh);
$('vod-form').addEventListener('submit',event => {
  event.preventDefault(); const url = safeVideoUrl($('vod-url').value.trim());
  if (!url) { $('vod-status').textContent = 'YouTube 또는 Twitch의 HTTPS 영상 주소를 입력하세요.'; return; }
  window.open(url.href,'_blank','noopener,noreferrer');
  $('vod-status').textContent = '영상 열기를 요청했습니다. 이 단계에서는 영상 분석이나 스킨 확인 기록을 저장하지 않습니다.';
});
render(); refresh();
