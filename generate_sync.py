#!/usr/bin/env python3
"""generate_sync.py — Generate a rythmo-band sync video.

Usage:
    python generate_sync.py <video_file> <script_file> [output.mp4]

Accepts: video (mp4, mov, mkv, avi) + script (xlsx, ods, csv, tsv, txt).
Reports progress as JSON lines to stderr for web integration:
    {"progress": 42, "frame": 2100, "total": 5000, "phase": "render"}
"""

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

# ── Output ────────────────────────────────────────────────────────
OUTPUT_W, OUTPUT_H = 1280, 720
PLAYHEAD_X = 240
SCROLL_SPEED = 250
# If set (int), interpreted as pixels-per-frame and converted to px/sec inside generate()
PX_PER_FRAME = None
FONT_SIZE = 48
MIN_ROW_H = 55
MAX_ROW_H = 90
MIN_VIDEO_H = 300

LINE_COLOR = (180, 180, 180)
PLAYHEAD_COLOR = (200, 0, 0)

PALETTE = [
    (140, 0, 200), (0, 0, 0), (0, 90, 190), (190, 70, 0),
    (0, 130, 0), (190, 0, 50), (100, 100, 0), (0, 140, 140),
]

TC_RE = re.compile(r'^\d{1,2}:\d{2}:\d{2}[:.]\d{1,3}$')
VIDEO_EXTS = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}
SCRIPT_EXTS = {'.xlsx', '.xls', '.ods', '.csv', '.tsv', '.txt'}

FPS_CONFIG_FILE = Path(__file__).resolve().parent / 'FPS.txt'
DEFAULT_FPS = 50.0


def read_fps_config() -> float:
    """Read the render frame-rate from FPS.txt (repo root). Falls back to DEFAULT_FPS."""
    try:
        value = FPS_CONFIG_FILE.read_text(encoding='utf-8').strip().splitlines()[0].strip()
        fps = float(value)
        if fps <= 0:
            raise ValueError('FPS must be positive')
        return fps
    except Exception as exc:
        print(f'Warning: could not read {FPS_CONFIG_FILE.name} ({exc}); using {DEFAULT_FPS} fps.',
              file=sys.stderr)
        return DEFAULT_FPS


def report(phase: str, progress: int, frame: int = 0, total: int = 0):
    """Emit JSON progress line to stderr."""
    msg = {"progress": progress, "frame": frame, "total": total, "phase": phase}
    print(json.dumps(msg), file=sys.stderr, flush=True)


def tc_to_seconds(tc: str, fps: float = 25.0) -> float:
    parts = str(tc).strip().split(':')
    if len(parts) == 4:
        try:
            h, m, s, f = map(int, parts)
            return h * 3600 + m * 60 + s + f / fps
        except ValueError:
            pass
    if len(parts) == 3:
        # HH:MM:SS or MM:SS:FF — try HH:MM:SS first
        try:
            h, m, s = map(int, parts)
            if h < 24:
                return h * 3600 + m * 60 + s
        except ValueError:
            pass
    try:
        return float(pd.to_timedelta(tc).total_seconds())
    except Exception:
        return 0.0


def find_font(size: int):
    candidates = [
        "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
        "/Library/Fonts/Bradley Hand Bold.ttf",
        "/System/Library/Fonts/Noteworthy.ttc",
        "/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf",
        "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default(size)


# ── Script readers ────────────────────────────────────────────────

def read_spreadsheet(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    # dtype=str prevents openpyxl/odf from trying to parse dates/times,
    # which causes "The string did not match the expected pattern" errors.
    if ext == '.ods':
        df = pd.read_excel(path, engine='odf', header=None, dtype=str)
    elif ext == '.xlsx':
        df = pd.read_excel(path, engine='openpyxl', header=None, dtype=str)
    elif ext == '.xls':
        # old-style Excel (.xls) — use xlrd engine which supports BIFF files
        try:
            df = pd.read_excel(path, engine='xlrd', header=None, dtype=str)
        except Exception:
            # let caller handle the exception (e.g., BadZipFile or ImportError)
            raise
    else:
        raise ValueError(f'Unsupported spreadsheet format: {ext}')

    first_row = [str(v).strip() for v in df.iloc[0]]
    import re as _re
    _HEADER_KW = _re.compile(
        r'\b(char|perso|personnage|script|texte|text|time|tc in|tc out|tc_in|tc_out|'
        r'dialogue|scene|role|r\u00f4le|r\u00e9plique|line|d\u00e9but|debut|fin)\b',
        _re.IGNORECASE)
    looks_like_header = any(_HEADER_KW.search(v) for v in first_row)
    if looks_like_header:
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
    return df


def read_text_script(path: Path) -> pd.DataFrame:
    """Read CSV / TSV / TXT script file.
    Tries tab-separated first, then semicolon, then comma.
    Supports with or without header."""
    # Try UTF-8, fallback to latin-1
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        text = path.read_text(encoding='latin-1')
    lines = [l for l in text.strip().splitlines() if l.strip()]
    if not lines:
        raise ValueError(f'Empty script file: {path}')

    # Detect delimiter
    for delim in ['\t', ';', ',']:
        sample = lines[0].split(delim)
        if len(sample) >= 3:
            break
    else:
        delim = '\t'

    reader = csv.reader(lines, delimiter=delim)
    rows = list(reader)

    # Check header
    header_kw = ('char', 'perso', 'script', 'text', 'time', 'tc',
                 'dialogue', 'scene', 'role', 'in', 'out')
    first = rows[0]
    has_header = any(any(k in c.lower() for k in header_kw) for c in first)

    if has_header:
        df = pd.DataFrame(rows[1:], columns=first)
    else:
        df = pd.DataFrame(rows)
    return df


def read_script(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext in ('.xlsx', '.xls', '.ods'):
        return read_spreadsheet(path)
    elif ext in ('.csv', '.tsv', '.txt'):
        return read_text_script(path)
    else:
        raise ValueError(
            f'Unsupported script format: {ext}. '
            f'Supported: {", ".join(sorted(SCRIPT_EXTS))}')


def detect_columns(df: pd.DataFrame):
    char_col = start_col = end_col = text_col = None

    for c in df.columns:
        lc = str(c).strip().lower()
        if char_col is None and any(k in lc for k in
                ('character', 'char', 'personnage', 'perso', 'actor', 'acteur',
                 'role', 'rôle')):
            char_col = c
        if start_col is None and any(k in lc for k in
                ('tc in', 'tc_in', 'tcin', 'start time', 'start_time',
                 'time in', 'time_in', 'début', 'debut', 'in')):
            start_col = c
        if end_col is None and any(k in lc for k in
                ('tc out', 'tc_out', 'tcout', 'end time', 'end_time',
                 'time out', 'time_out', 'fin', 'out')):
            end_col = c
        if text_col is None and any(k in lc for k in
                ('script', 'texte', 'text', 'dialogue', 'réplique', 'replique',
                 'line')):
            text_col = c

    if start_col == end_col:
        start_col = end_col = None
        for c in df.columns:
            lc = str(c).strip().lower()
            if 'in' in lc and start_col is None:
                start_col = c
            elif 'out' in lc and end_col is None:
                end_col = c

    # Positional fallback for header-less files
    missing = [x is None for x in (char_col, start_col, end_col, text_col)]
    if any(missing) and len(df.columns) >= 3:
        sample = df.iloc[0]
        tc_cols, str_cols = [], []
        for c in df.columns:
            val = str(sample[c]).strip()
            if TC_RE.match(val):
                tc_cols.append(c)
            elif val and val.lower() != 'nan':
                str_cols.append(c)
        if len(tc_cols) >= 2 and len(str_cols) >= 1:
            if start_col is None:
                start_col = tc_cols[0]
            if end_col is None:
                end_col = tc_cols[1]
            if len(str_cols) >= 2:
                str_lens = [(c, df[c].astype(str).str.len().mean())
                            for c in str_cols]
                str_lens.sort(key=lambda x: x[1])
                if char_col is None:
                    char_col = str_lens[0][0]
                if text_col is None:
                    text_col = str_lens[-1][0]
            else:
                if text_col is None:
                    text_col = str_cols[0]

    missing = []
    if char_col is None: missing.append('character')
    if start_col is None: missing.append('TC IN')
    if end_col is None: missing.append('TC OUT')
    if text_col is None: missing.append('script')
    if missing:
        raise ValueError(
            f'Could not detect columns: {", ".join(missing)}.\n'
            f'Available columns: {list(df.columns)}')

    return char_col, start_col, end_col, text_col


# ── Main generation ───────────────────────────────────────────────

def generate(video_path: Path, script_path: Path, out_path: Path,
             fps: float = None,
             tc_fps: float = 25.0):
    """Generate the sync video. Returns the output path.

    fps     : video render frame-rate. Defaults to the value in FPS.txt (50).
    tc_fps  : frame-rate used in the script timecodes (25fps by default).
    """
    if fps is None:
        fps = read_fps_config()
    report('read', 0)

    df = read_script(script_path)
    df = df.dropna(how='all').reset_index(drop=True)
    char_col, start_col, end_col, text_col = detect_columns(df)
    print(f'Columns: char={char_col!r}, in={start_col!r}, '
          f'out={end_col!r}, text={text_col!r}')

    phrases = []
    for _, row in df.iterrows():
        text = str(row[text_col]).strip()
        text = text.replace('_x000D_', ' ').replace('_X000D_', ' ')
        text = text.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
        text = ' '.join(text.split())
        char = str(row[char_col]).strip() if char_col is not None else 'Speaker'
        start = tc_to_seconds(row[start_col], tc_fps)
        end = tc_to_seconds(row[end_col], tc_fps)
        if end <= start or not text:
            continue
        phrases.append({'text': text, 'char': char, 'start': start, 'end': end})

    if not phrases:
        raise ValueError('No valid phrases found in the script.')

    # If all TCs are offset by a whole number of hours (e.g. 01:00:00:00),
    # subtract that hour offset so the video starts at t=0.
    min_start = min(p['start'] for p in phrases)
    if min_start >= 3600 and min_start % 3600 == 0:
        offset = min_start
        for p in phrases:
            p['start'] -= offset
            p['end']   -= offset

    chars_ordered = list(dict.fromkeys(p['char'] for p in phrases))
    char_color = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(chars_ordered)}
    n_rows = len(chars_ordered)
    print(f'Characters ({n_rows}): {chars_ordered}')

    # ── LRU lane assignment (max 8 lanes) ────────────────────────
    MAX_LANES = 8
    if n_rows > MAX_LANES:
        sorted_phrases = sorted(phrases, key=lambda p: p['start'])
        lane_for_char = {}       # char -> current lane index
        lane_state = {}          # lane -> (char, last_end_sec)
        lane_schedule = [[] for _ in range(MAX_LANES)]  # lane -> [(start_sec, char)]
        for p in sorted_phrases:
            char = p['char']
            if char in lane_for_char:
                lane = lane_for_char[char]
                p['lane'] = lane
                lane_state[lane] = (char, p['end'])
            elif len(lane_state) < MAX_LANES:
                lane = len(lane_state)
                lane_state[lane] = (char, p['end'])
                lane_for_char[char] = lane
                lane_schedule[lane].append((p['start'], char))
                p['lane'] = lane
            else:
                candidates = sorted(
                    (lo, ln, c) for ln, (c, lo) in lane_state.items()
                    if lo <= p['start'])
                if not candidates:
                    candidates = sorted(
                        (lo, ln, c) for ln, (c, lo) in lane_state.items())
                _, old_lane, old_char = candidates[0]
                del lane_for_char[old_char]
                lane_for_char[char] = old_lane
                lane_state[old_lane] = (char, p['end'])
                lane_schedule[old_lane].append((p['start'], char))
                p['lane'] = old_lane
        effective_n_rows = MAX_LANES
        print(f'LRU: {n_rows} chars → {MAX_LANES} lanes')
    else:
        lane_schedule = [[(0, chars_ordered[i])] for i in range(n_rows)]
        for p in phrases:
            p['lane'] = chars_ordered.index(p['char'])
        effective_n_rows = n_rows

    row_h = max(MIN_ROW_H, min(MAX_ROW_H, (OUTPUT_H - MIN_VIDEO_H) // effective_n_rows))
    rythmo_h = row_h * effective_n_rows
    rythmo_top = OUTPUT_H - rythmo_h
    vid_area_h = rythmo_top
    print(f'Layout: video {OUTPUT_W}x{vid_area_h}, rythmo {rythmo_h}px '
          f'({effective_n_rows} rows x {row_h}px)')

    max_end = max(p['end'] for p in phrases)

    # determine effective scroll speed (px/sec). If PX_PER_FRAME is provided,
    # use px/frame * fps; otherwise use SCROLL_SPEED (px/sec).
    effective_scroll_speed = SCROLL_SPEED
    try:
        if PX_PER_FRAME:
            effective_scroll_speed = int(PX_PER_FRAME) * int(fps)
    except Exception:
        effective_scroll_speed = SCROLL_SPEED

    # Open video early; needed for its native dimensions/duration during rendering.
    from moviepy.video.io.VideoFileClip import VideoFileClip
    vid = VideoFileClip(str(video_path))

    band_total_px = int(max_end * effective_scroll_speed) + OUTPUT_W + PLAYHEAD_X
    print(f'Band width: {band_total_px}px for {max_end:.1f}s @ {effective_scroll_speed} px/s')

    report('strips', 5)
    effective_font_size = min(FONT_SIZE, row_h - 12)
    font = find_font(effective_font_size)
    label_font = find_font(max(16, row_h // 3))
    measure_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))

    print('Pre-rendering rythmo strips …')
    strips = {}
    for lane in range(effective_n_rows):
        strip = Image.new('RGBA', (band_total_px, row_h), (255, 255, 255, 255))
        strip_draw = ImageDraw.Draw(strip)
        for p in phrases:
            if p.get('lane') != lane:
                continue
            char = p['char']
            color = char_color[char]
            x_start = int(p['start'] * effective_scroll_speed)
            x_end = int(p['end'] * effective_scroll_speed)
            alloc_w = x_end - x_start
            if alloc_w < 5:
                continue
            bbox = measure_draw.textbbox((0, 0), p['text'], font=font)
            natural_w = bbox[2] - bbox[0]
            natural_h = bbox[3] - bbox[1]
            tmp = Image.new('RGBA', (natural_w + 6, natural_h + 6), (0, 0, 0, 0))
            td = ImageDraw.Draw(tmp)
            td.text((-bbox[0] + 3, -bbox[1] + 3), p['text'], font=font,
                    fill=color + (255,))
            target_h = natural_h + 6
            target_w = int(alloc_w * 0.92)
            resized = tmp.resize((target_w, target_h), Image.LANCZOS)
            y_offset = (row_h - target_h) // 2
            margin_x = (alloc_w - target_w) // 2
            strip.paste(resized, (x_start + margin_x, y_offset), resized)
        # Option D: lane-change markers (vertical line + new char name)
        for k, (start_sec, char) in enumerate(lane_schedule[lane]):
            if k == 0:
                continue
            x_mark = int(max(0.0, start_sec - 1.5) * effective_scroll_speed)
            color = char_color[char]
            strip_draw.line([(x_mark, 0), (x_mark, row_h)], fill=color + (255,), width=3)
            lbl_bbox = measure_draw.textbbox((0, 0), char, font=label_font)
            lw = lbl_bbox[2] - lbl_bbox[0]
            lh = lbl_bbox[3] - lbl_bbox[1]
            mx = x_mark + 5
            my = (row_h - lh) // 2 - lbl_bbox[1]
            strip_draw.rectangle([mx - 2, row_h // 4, mx + lw + 4, 3 * row_h // 4],
                                  fill=(255, 255, 220, 230))
            strip_draw.text((mx, my), char, font=label_font, fill=color + (255,))
        strips[lane] = strip
    print('Strips rendered.')

    # Overlay — static: row dividers + playhead. Labels drawn dynamically per frame.
    overlay = Image.new('RGBA', (OUTPUT_W, rythmo_h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(effective_n_rows + 1):
        od.line([(0, i * row_h), (OUTPUT_W, i * row_h)],
                fill=LINE_COLOR + (255,), width=1)
    od.line([(PLAYHEAD_X, 0), (PLAYHEAD_X, rythmo_h)],
            fill=PLAYHEAD_COLOR + (255,), width=2)

    # Pre-render one label image per character for fast per-frame compositing
    LABEL_MARGIN = 8
    label_imgs = {}
    for char in chars_ordered:
        color = char_color[char]
        lbl_bbox = measure_draw.textbbox((0, 0), char, font=label_font)
        lw = lbl_bbox[2] - lbl_bbox[0]
        lh = lbl_bbox[3] - lbl_bbox[1]
        lbl_img = Image.new('RGBA', (lw + 12, row_h), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lbl_img)
        ld.rectangle([0, 2, lw + 10, row_h - 2], fill=(255, 255, 255, 220))
        ld.text((LABEL_MARGIN - lbl_bbox[0], (row_h - lh) // 2 - lbl_bbox[1]),
                char, font=label_font, fill=color + (255,))
        label_imgs[char] = lbl_img

    # Video
    report('video', 10)
    total_frames = int(vid.duration * fps)

    scale = min(OUTPUT_W / vid.w, vid_area_h / vid.h)
    new_w, new_h = int(vid.w * scale), int(vid.h * scale)
    vid_x = (OUTPUT_W - new_w) // 2
    vid_y = (vid_area_h - new_h) // 2

    # Look for an external audio file in the VI/ directory matching the video's stem.
    repo_root = Path(__file__).resolve().parent
    vi_dir = repo_root / 'VI'
    audio_path = None
    if vi_dir.exists():
        for ext in ('.m4a', '.aac', '.wav', '.mp3'):
            candidate = vi_dir / f"{video_path.stem}{ext}"
            if candidate.exists():
                audio_path = candidate
                break

    # Build ffmpeg command. Inputs: rawvideo stdin, video file, [optional audio file].
    # Uses the portable ffmpeg binary bundled by imageio_ffmpeg (same one
    # moviepy uses internally) so no system/Homebrew ffmpeg install is needed.
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-hide_banner', '-loglevel', 'warning',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', f'{OUTPUT_W}x{OUTPUT_H}', '-pix_fmt', 'rgb24',
        '-r', str(int(fps)), '-i', '-',
        '-i', str(video_path),
    ]

    use_external_audio = audio_path is not None
    if use_external_audio:
        cmd += ['-i', str(audio_path)]

    # Mapping: video from stdin, audio from either external file or from the input video.
    if use_external_audio:
        audio_map = '2:a'
    else:
        audio_map = '1:a'

    # Choose audio codec: copy if container/codecs are compatible (m4a/aac), otherwise encode to AAC.
    if use_external_audio and audio_path.suffix.lower() in ('.m4a', '.aac'):
        audio_codec_args = ['-c:a', 'copy']
    else:
        audio_codec_args = ['-c:a', 'aac']

    cmd += [
        '-map', '0:v', '-map', audio_map,
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
        '-pix_fmt', 'yuv420p',
    ] + audio_codec_args + ['-shortest', str(out_path)]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    frame_buf = np.zeros((OUTPUT_H, OUTPUT_W, 3), dtype=np.uint8)

    print(f'Rendering {total_frames} frames @ {int(fps)} fps …')
    for fi in range(total_frames):
        t = fi / fps
        band_offset = int(t * effective_scroll_speed)
        crop_x0 = band_offset - PLAYHEAD_X
        crop_x1 = crop_x0 + OUTPUT_W

        frame_buf[:] = 0
        try:
            vf = vid.get_frame(t)
            vimg = Image.fromarray(vf).resize((new_w, new_h), Image.BILINEAR)
            frame_buf[vid_y:vid_y + new_h, vid_x:vid_x + new_w] = np.array(vimg)
        except Exception:
            pass

        band = Image.new('RGB', (OUTPUT_W, rythmo_h), (255, 255, 255))
        for lane in range(effective_n_rows):
            strip = strips[lane]
            sx0 = max(0, crop_x0)
            sx1 = min(band_total_px, crop_x1)
            if sx1 <= sx0:
                continue
            row_crop = strip.crop((sx0, 0, sx1, row_h))
            dx = sx0 - crop_x0
            band.paste(row_crop, (dx, lane * row_h), row_crop)

        band.paste(overlay, (0, 0), overlay)
        # Dynamic left-side labels: show which char currently owns each lane
        for lane in range(effective_n_rows):
            current_char = lane_schedule[lane][0][1]
            for start_sec, char in lane_schedule[lane]:
                if start_sec - 1.5 <= t:
                    current_char = char
            lbl_img = label_imgs.get(current_char)
            if lbl_img:
                band.paste(lbl_img, (LABEL_MARGIN - 4, lane * row_h), lbl_img)
        frame_buf[rythmo_top:rythmo_top + rythmo_h, :] = np.array(band)
        try:
            proc.stdin.write(frame_buf.tobytes())
        except BrokenPipeError:
            break

        if fi % 50 == 0:
            pct = 10 + fi * 89 // total_frames
            report('render', pct, fi, total_frames)
        if fi % 250 == 0:
            pct_display = fi * 100 // total_frames
            print(f'\r  {pct_display:3d}% ({fi}/{total_frames})',
                  end='', flush=True)

    proc.stdin.close()
    stderr = proc.stderr.read()
    rc = proc.wait()
    vid.close()

    if rc != 0:
        raise RuntimeError(f'FFmpeg error:\n{stderr.decode()}')

    report('done', 100, total_frames, total_frames)
    print(f'\r  100% — Done → {out_path}')
    return out_path


def main():
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <video> <script> [output.mp4]',
              file=sys.stderr)
        sys.exit(1)

    video_path = Path(sys.argv[1])
    script_path = Path(sys.argv[2])

    if not video_path.exists():
        print(f'Video not found: {video_path}', file=sys.stderr)
        sys.exit(1)
    if not script_path.exists():
        print(f'Script not found: {script_path}', file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) >= 4:
        out_path = Path(sys.argv[3])
    else:
        out_path = video_path.parent / f'{video_path.stem}_Sync.mp4'

    # parse optional CLI flag: --px-per-frame <int>
    global PX_PER_FRAME
    try:
        if '--px-per-frame' in sys.argv:
            i = sys.argv.index('--px-per-frame')
            PX_PER_FRAME = int(sys.argv[i+1])
    except Exception:
        PX_PER_FRAME = None

    # parse optional CLI flag: --fps <value> (overrides FPS.txt)
    fps = None
    try:
        if '--fps' in sys.argv:
            i = sys.argv.index('--fps')
            fps = float(sys.argv[i+1])
    except Exception:
        fps = None

    generate(video_path, script_path, out_path, fps=fps)


if __name__ == '__main__':
    main()
