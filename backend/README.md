# 컬렉션 자동 확인 서버

사이트 접속(서버 연결 후) → 라이브 찾기 → 라이브가 없으면 최신 공개 다시보기 → 일정 간격 화면 분석 → 장착 컬렉션을 연속 두 프레임에서 확인 → 영상 수신 즉시 종료 → 보관한 두 화면과 카탈로그 참조 이미지 비교 → 일치한 스킨만 결과 저장 → 사이트 최신화.

게임 플레이, 상점, 스킨 목록을 장착 컬렉션으로 취급하지 않습니다. 컬렉션을 발견했지만 확정할 스킨이 없어도 영상을 종료합니다. AI의 두 프레임 판별과 참조 비교는 오인식 가능성이 있어 사람의 확인과 동일하지 않습니다. 일부 스킨만 식별하면 나머지 무기는 기존 기록을 유지하고 무기별 확인 날짜를 표시합니다. 카탈로그에 없는 신규 스킨은 미확인입니다.

## 필요한 설정

- 영상 접근이 가능한 서버, Python 3.12, FFmpeg, Node.js
- OPENAI_API_KEY: 서버 환경 변수에만 저장하는 이미지 분석용 키
- SCAN_TOKEN: 긴 임의 분석 암호. 사이트 연결 폼에도 같은 값 사용
- 선택 GITHUB_TOKEN: K3ANER/val-live Contents 쓰기 권한만 있는 토큰. 없어도 서버 결과를 조회해 사이트 최신화 가능

실제 키는 GitHub나 채팅에 올리지 마세요. ChatGPT Plus와 API 요금은 별개입니다. 코드 작성 과정에서 유료 서버 구입, API 결제, 서버 배포를 실행하지 않았습니다.

## 로컬 실행

저장소 최상위에서:

```sh
python3 -m pip install -r backend/requirements.txt
export OPENAI_API_KEY='서버에서만 입력'
export SCAN_TOKEN='긴 분석 암호'
export DATA_DIR='/tmp/val-live-data'
python3 -m flask --app backend.app run --host 127.0.0.1 --port 8080
```

http://127.0.0.1:8080 에서 분석 서버 주소에 http://127.0.0.1:8080, 암호에 SCAN_TOKEN을 입력합니다. .env.example은 자동으로 읽지 않습니다. 서버 환경 변수를 설정하세요.

모바일 데이터망에서 사용하려면 HTTPS 서버 배포가 필요합니다. Dockerfile과 render.yaml은 Render Starter 유료 계획 및 결과 보관 디스크의 배포 예시입니다. 저장소 K3ANER/val-live 연결 후 OPENAI_API_KEY, SCAN_TOKEN을 비밀 환경 변수로 지정하세요. 배포된 HTTPS 기본 주소를 사이트 연결 폼에 입력합니다. 분석 암호는 브라우저 세션 저장소에만 유지되고 API 키를 사이트에 입력하지 않습니다.

## 제한과 비용

기본 5초마다 한 프레임, 최대 120프레임(다시보기 약 10분 범위)이며 전체 영상을 다운로드하지 않고 프레임 스트림만 읽습니다. 한 프레임 판별당 API 호출 1회, 참조 비교 최대 19회가 추가됩니다. FRAME_INTERVAL, MAX_FRAMES로 범위를 조정할 수 있습니다. 기본 모델 gpt-4.1은 VISION_MODEL로 변경 가능합니다.

라이브는 실행 시점 이후만 확인합니다. 과거 DVR 자동 탐색은 구현하지 않았습니다. 짧게 표시되거나 연속 두 프레임에 잡히지 않는 컬렉션을 놓칠 수 있습니다. 전체 다시보기 무제한 탐색이나 지속 감시 기능은 아닙니다.

최대 벽시계 실행 시간 20분이며 개별 요청 제한 시간만큼 초과할 수 있습니다. 중지 요청은 현재 API 호출/프레임 수신이 종료되는 대로 적용됩니다. 이미 진행된 API 호출 비용은 취소되지 않습니다. 한 서버 프로세스, 시작 간격 1분, 동시 작업 1개입니다. 성공 후 30분 내 접속 시 기존 결과를 재사용하며 최신화 버튼은 재검사를 요청합니다.

서버 재시작 시 실행 중 작업이 중단됩니다. 결과 유지에는 영구 디스크가 필요합니다. YouTube/Twitch의 로그인·지역·접근 제한에 걸리면 오류를 표시하며 제한을 우회하지 않습니다.

## API

- GET /api/health: 필수 설정 존재 여부, 실제 키 유효성 검증 아님
- GET /api/latest: 공개 결과 JSON
- GET /api/status: 진행/종료 상태
- POST /api/analyze: Bearer SCAN_TOKEN, {"player":"TenZ","force":false,"url":""}. URL 생략 시 라이브/최신 다시보기
- POST /api/cancel: 동일 인증, 중지

ALLOWED_ORIGINS 기본값은 https://k3aner.github.io이며 쉼표로 추가할 수 있습니다. Docker는 gunicorn workers=1로 실행합니다.

## 검증

`python3 -m unittest discover -s tests -v`

모의 비전 응답으로 컬렉션 뒤 추가 프레임 수신 종료, 참조 불일치 거부, 두 프레임 합의, 취소, 인증/CORS를 검증합니다. 실제 영상 식별 정확도는 API 키와 영상 접근 가능한 서버에서 추가 검증해야 합니다. 이 코드의 구현 완료가 실제 배포·스킨 식별 성공을 의미하지 않습니다.

카탈로그: https://valorant-api.com/v1/weapons (커뮤니티 API이며 Riot 공식 API 아님)
비전 API: https://developers.openai.com/api/docs/guides/images-vision
