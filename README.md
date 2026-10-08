# VAL-LIVE 자동 영상 검색 + 스킨 이미지 인식
TenZ, aspas, t3xture, something의 공개 YouTube/Twitch VOD를 무료 GitHub Actions에서 검색하고, 컬렉션 화면이 나타난 경우 스킨명 OCR 및 무료 [Valorant-API](https://valorant-api.com/) 아이콘 이미지 대조를 수행합니다.

## 실제 작동 범위
- 영상 주소 **직접 입력 불필요**: `sources.json`의 채널을 자동 탐색
- 6시간마다 자동 검색/분석 (GitHub Actions 무료 사용량 범위)
- 공개 비디오만 다운로드 가능. 로그인/DRM/접근 제한을 우회하지 않음.
- COLLECTION 화면을 OCR로 판별하고 텍스트 또는 이미지가 두 프레임에서 일치하면 `latest.json`에 검증 처리
- 기존 검증 결과 유지. 확신하지 못하는 스킨은 '미확인'
- 모바일/PC 웹 인터페이스 (GitHub Pages)

## 시작
GitHub Actions → 'VAL-LIVE – 무료 OCR 및 스킨 이미지 자동 비교' → Run workflow.
스케줄 실행은 Actions가 허용되어 있으면 6시간마다 자동 시도됩니다.
GitHub Pages가 아직 미설정이라면 Settings → Pages → Deploy from a branch → main → /(root).

## 원클릭 버튼의 제약
GitHub Pages는 정적 호스팅으로 비밀 토큰을 안전하게 보관할 수 없어 웹 버튼만으로 GitHub Actions 작업을 실행할 수 없습니다. 별도 Worker 또는 로그인이 필요한 GitHub Actions 수동 실행이 필요합니다. Worker 토큰을 브라우저에 넣지 마세요. 서버 미설정 상태에서는 최신화 버튼이 이미 분석된 결과만 새로 불러옵니다.

## 이미지 인식 한계
무료 아이콘 비교는 컬렉션의 평면 총기 아이콘과 일치할 때만 유효하며, 3D 게임 플레이 중 총기 스킨 인식기는 아닙니다. 자동 탐색 실패나 유사한 스킨 사이의 오인식 가능성이 있습니다. 공개 VOD 실제 성공 여부는 GitHub Actions의 실행 기록으로 확인하세요.
