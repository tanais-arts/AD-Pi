"""batch_sync.py — Régénère toutes les vidéos sync (fps défini dans FPS.txt).
Sortie dans AD/VIDEOS/SYNC/<stem>_Sync.mp4

Usage:
    python batch_sync.py [--force]

    --force  : régénère même si le fichier de sortie existe déjà
"""
import sys
import subprocess
from pathlib import Path

BASE   = Path(__file__).parent
VIDEOS = BASE / 'VIDEOS'
SCRIPTS = BASE / 'SCRIPTS'
OUT_DIR = VIDEOS / 'SYNC'
OUT_DIR.mkdir(exist_ok=True)

FORCE = '--force' in sys.argv

video_files = sorted(VIDEOS.glob('*.mp4'))
pairs = []
for v in video_files:
    s = SCRIPTS / f'{v.stem}.xlsx'
    if s.exists():
        pairs.append((v, s))
    else:
        print(f'[SKIP] Pas de script pour {v.name}')

print(f'{len(pairs)} paires trouvées.\n')

ok = 0
errors = []
for i, (video, script) in enumerate(pairs, 1):
    out = OUT_DIR / f'{video.stem}_Sync.mp4'
    if out.exists() and not FORCE:
        print(f'[{i}/{len(pairs)}] EXISTE déjà — {out.name}')
        ok += 1
        continue
    print(f'[{i}/{len(pairs)}] {video.stem} …')
    result = subprocess.run(
        [sys.executable, str(BASE / 'generate_sync.py'),
         str(video), str(script), str(out)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f'  OK → {out.name}')
        ok += 1
    else:
        print(f'  ERREUR:\n{result.stderr[-400:]}')
        errors.append(video.stem)

print(f'\n=== {ok}/{len(pairs)} OK', end='')
if errors:
    print(f'  |  {len(errors)} erreurs: {", ".join(errors)}')
else:
    print(' — Tout est bon.')
