# VAL LIVE — K3ANER/val-live 초기 구조

빌드나 패키지 설치 없이 실행되는 모바일 대응 정적 사이트입니다.

| 파일 | 역할 |
| --- | --- |
| index.html | 첫 화면, 선수 선택, 스킨 확인, 다시보기 확인, 최신화 버튼 |
| assets/styles.css | 검정·빨강 테마, 모바일 레이아웃 |
| assets/app.js | 결과 조회, 무기 검색, 선수 전환, 영상 링크 검증 |
| data/latest.json | 선수별 확인 결과 데이터 |
| .nojekyll | 정적 파일 그대로 제공 |

## 로컬 실행

프로젝트 폴더에서 `python3 -m http.server 8000`을 실행하고 http://localhost:8000 을 엽니다. 파일을 직접 더블클릭하면 JSON 조회가 제한될 수 있습니다.

## GitHub에 적용

압축을 풀고 **val-live 폴더 안의 파일과 폴더**를 K3ANER/val-live 저장소 최상위에 올립니다. index.html이 저장소 최상위에 있어야 합니다. GitHub 웹 업로드 시 숨김 파일 .nojekyll도 포함하거나 별도로 만듭니다.

GitHub Pages를 사용할 경우 저장소 Settings → Pages에서 배포 브랜치의 루트 폴더를 선택합니다. 기본 예상 주소는 https://k3aner.github.io/val-live/ 입니다. 이 코드는 아직 저장소에 업로드하거나 배포하지 않았습니다.

## 실제로 동작하는 기능

- 19개 무기 슬롯(근접 무기 포함), 선수 선택, 검색
- 최신화: data/latest.json을 캐시 없이 다시 조회
- YouTube/Twitch HTTPS 영상 URL 검증 및 새 창 열기
- 로딩, 빈 결과, 요청 실패 표시 및 기존 결과 유지
- verified가 true이고 스킨 이름이 있는 기록만 확인된 스킨으로 표시

초기 데이터는 비어 있습니다. 선수의 실제 스킨, 라이브 상태, 확인 시간을 임의로 만들지 않았습니다. 최신화는 영상 수집·자동 분석을 실행하지 않습니다.

## 결과 데이터 규약

실제 검증한 결과에만 다음 필드를 입력합니다. checkedAt은 ISO 8601 시각, vod는 {"url":"영상의 HTTPS 주소", "title":"영상 제목"}, weapons는 무기 이름을 키로 하는 객체입니다. 무기별 값은 {"skin":"확인된 스킨 이름", "verified":true} 형태입니다. 미확인 기록은 verified:false 또는 빈 객체로 둡니다.

schemaVersion:1 → players → 선수 이름 → checkedAt / vod / weapons 구조를 유지합니다. 다른 데이터 규약은 app.js의 변환 단계가 필요합니다.

## 기존 연결 버전과 후속 통합

기존 VAL_LIVE_CONNECTED.zip의 server.py는 /api/analyze, /api/status, /api/latest를 제공하며 analyzer.py는 후보 화면 추출 단계입니다. 스킨 이름 자동 식별은 구현되어 있지 않습니다.

이 초기 사이트는 그 Python 서버를 실행하지 않습니다. 향후 서버 연결 시 POST /api/analyze로 작업 시작, GET /api/status로 완료 확인, GET /api/latest?player=TenZ로 결과 조회 후 이 프로젝트의 players 규약으로 변환하는 어댑터를 추가하세요. 기존 vod.webpage_url은 vod.url로 변환합니다. 확인 시각은 결과의 checkedAt을 사용하고 조회 시각으로 덮어쓰지 않습니다.

GitHub Pages는 정적 화면만 제공합니다. 영상 다운로드, 프레임 추출, 스킨 식별을 수행하려면 별도 분석 서버가 필요합니다. 공개 분석 API를 연결하기 전에 인증, 요청 제한, 작업 중복 방지와 URL 검증을 구현하세요. 비밀 키를 프런트엔드에 넣지 마세요.
