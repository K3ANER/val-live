import os
from pathlib import Path
PLAYERS = {
    'TenZ': 'https://www.youtube.com/@TenZ',
    't3xture': 'https://www.youtube.com/@t3xture_full',
    'aspas': 'https://www.twitch.tv/aspaszin',
    'something': 'https://www.youtube.com/@somethingfps',
}
WEAPONS = ['Classic','Shorty','Frenzy','Ghost','Sheriff','Stinger','Spectre','Bucky','Judge','Bulldog','Guardian','Phantom','Vandal','Marshal','Outlaw','Operator','Ares','Odin','Melee']
DATA_DIR = Path(os.getenv('DATA_DIR', '/tmp/val-live-data'))
MODEL = os.getenv('VISION_MODEL', 'gpt-4.1')
MAX_FRAMES = max(2, min(600, int(os.getenv('MAX_FRAMES', '120'))))
INTERVAL = max(1, int(os.getenv('FRAME_INTERVAL', '5')))
