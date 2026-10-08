# VAL LIVE video scanner

This is an **optional, manual GitHub Actions prototype** for an **authorized direct MP4** video file. It does **not** download or automatically watch YouTube/Twitch VODs. It samples one frame every 20 seconds with ffmpeg, calls a vision model, stops at the first collection screen with readable weapon skins, and writes AI **candidate** results to latest.json. Results are unverified until human review; false positives are possible.

## Setup
1. In repository Settings > Secrets and variables > Actions, add OPENAI_API_KEY. API usage costs money.
2. In Actions > VAL LIVE authorized video scan > Run workflow, choose player and provide a direct HTTPS MP4 URL for video you are authorized to process.
3. GitHub Actions needs write permissions to commit (Settings > Actions > General > Workflow permissions > Read and write).
4. The homepage loads latest.json when opened or when '최신화' is pressed. It does **not** launch the scanner by itself.

YouTube watch links are not supported as direct media URLs. Do not bypass platform access restrictions. GitHub Actions runtime and remote media sizes are limited. The scanner does not guarantee finding the loadout and does not identify skins from gameplay.
