# VAL-LIVE: 발로란트 영상만 고속 탐색 (무료)
선수: TenZ, aspas, t3xture, something.

## 분석 과정
1. 지정한 유튜브·트위치 채널에서 **실제 재생 가능한 공개 VOD** 주소를 자동 수집합니다 (주소 직접 입력 불필요).
2. 영상 전체를 정상 속도로 보는 대신 시작/중간/끝을 포함한 **최대 5개의 짧은 구간**만 추출합니다. 각 구간에서 **24초마다 1프레임**을 OCR로 검사합니다.
3. 'BUY PHASE', 'SPIKE PLANTED' 등 발로란트 HUD 또는 발로란트 **COLLECTION** 화면으로 확인되지 않은 구간은 **상세 분석을 건너뜁니다**.
4. 발로란트 화면이 확인된 구간에서만 **4초마다 1프레임**을 추출해 COLLECTION에 있는 스킨 이름 OCR / 무료 Valorant-API 스킨 아이콘 이미지 비교를 실행합니다.
5. 다른 프레임 2개에서 동일 스킨을 확인한 경우에만 `latest.json`에 확정합니다. 게임 화면에서 스킨을 추정해서 등록하지 않습니다. 확신이 없다면 '미확인'으로 표시합니다.
6. GitHub Actions는 6시간마다 새 VOD를 발견해 검사하고, 결과를 GitHub Pages로 자동 게시합니다.

## 제한
- **3D 실전 총기 스킨 인식**은 아직 지원하지 않습니다. 확인 방법은 컬렉션 화면의 이미지 또는 텍스트 비교입니다.
- 녹화 전체를 빠짐없이 확인하는 것은 아닙니다. **스킵 샘플링**이기 때문에 짧은 컬렉션 화면이 샘플 구간 밖에 있으면 놓칠 수 있습니다.
- OCR 기반 VALORANT 여부 판정이므로 화면에 HUD 텍스트가 잘 안 보이면 발로란트 방송이라도 건너뛸 수 있습니다.
- 공개되어도 유튜브/트위치 다운로드 제한에 걸리면 분석할 수 없습니다. 제한을 우회하지 않습니다.
- GitHub Actions 무료 사용량에 한도가 있습니다. 별도 유료 AI API 키는 필요 없습니다.
- GitHub Pages의 최신화 버튼은 현재 저장된 결과를 갱신하는 기능입니다. 안전한 인증 서버가 없는 상태에서 웹 브라우저가 Actions를 직접 실행할 수는 없습니다. 화면의 "GitHub에서 즉시 분석 실행" 링크로 수동 실행하거나, 6시간마다 예약된 실행을 사용하세요.

## 설치/확인
- GitHub 저장소: https://github.com/K3ANER/val-live
- 모바일: https://k3aner.github.io/val-live/
- Actions: https://github.com/K3ANER/val-live/actions/workflows/scan.yml
- 빠른 스캔 단위 테스트: `python -m unittest discover -s tests -p 'test_fast_scan.py' -v`
