from server import _stem_tokens, find_matching_scripts, SCRIPTS_DIR, VIDEOS_DIR
from pathlib import Path

scripts = [f.name for f in SCRIPTS_DIR.iterdir() if f.is_file()]
print(f"SCRIPTS_DIR: {SCRIPTS_DIR}")
print(f"All scripts: {scripts}")
for s in scripts:
    print(f"  script: {s} -> tokens: {_stem_tokens(s)}")

videos = [f.name for f in VIDEOS_DIR.iterdir() if f.is_file()]
v = "AgeDeGlace_Extrait01.mp4"
print(f"\nExample video: {v} -> tokens: {_stem_tokens(v)}")
