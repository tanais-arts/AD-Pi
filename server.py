#!/usr/bin/env python3
"""server.py — Web server for rythmo sync video generation.

Upload a video + script → generate sync video → download.
Progress streamed via Server-Sent Events (SSE).

Usage:
    python server.py [--port 8080]
"""

import csv
import json
import os
import zipfile
import re
import shutil
import socket
import subprocess
import sys
import secrets
import threading
import time
import unicodedata
import uuid
from pathlib import Path
import pyphen
import signal
import hashlib
import hmac

from flask import (Flask, Response, jsonify, request, send_file,
                   send_from_directory)

app = Flask(__name__)

# Configurable content directories (video/scripts/VI reference audio) and the
# repartition CSV path. Overridable via config.json (written by the Setup tab
# or the PKG installer's first-run wizard); fall back to the historical
# hardcoded relative paths for existing deployments without a config.json.
CONFIG_FILE = Path('config.json')
_PATHS_DEFAULTS = {
    'videos_dir': 'VIDEOS',
    'scripts_dir': 'SCRIPTS',
    'vi_dir': 'VI',
    'repartition_csv': 'repartition.csv',
    'port': '1348',
}


def _load_paths_config():
    cfg = dict(_PATHS_DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
            for k in _PATHS_DEFAULTS:
                if data.get(k):
                    cfg[k] = data[k]
        except Exception:
            pass
    return cfg


def save_paths_config(new_values: dict):
    """Merge new_values into config.json (only known path keys are kept)."""
    cfg = _load_paths_config()
    for k in _PATHS_DEFAULTS:
        if k in new_values and new_values[k]:
            cfg[k] = new_values[k]
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
    return cfg


_PATHS_CFG = _load_paths_config()

UPLOAD_DIR = Path('uploads')
OUTPUT_DIR = Path('outputs')
VIDEOS_DIR = Path(_PATHS_CFG['videos_dir'])
SCRIPTS_DIR = Path(_PATHS_CFG['scripts_dir'])
VI_DIR = Path(_PATHS_CFG['vi_dir'])
REPARTITION_CSV = Path(_PATHS_CFG['repartition_csv'])
GENERATED_DIR = Path('GENERATED')
SESSIONS_DIR = Path('sessions')
for _d in (UPLOAD_DIR, OUTPUT_DIR, VIDEOS_DIR, SCRIPTS_DIR, VI_DIR, GENERATED_DIR, SESSIONS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
if not REPARTITION_CSV.exists():
    try:
        REPARTITION_CSV.parent.mkdir(parents=True, exist_ok=True)
        REPARTITION_CSV.write_text(
            'Fichier vidéo,Nombre de personnages,F,H,catégorie,SPEED,Afficher\n',
            encoding='utf-8-sig')
    except Exception:
        pass

# Directory used for Let's Encrypt HTTP-01 webroot challenges
WELL_KNOWN_DIR = Path('.well-known') / 'acme-challenge'
WELL_KNOWN_DIR.mkdir(parents=True, exist_ok=True)

# optional holding dirs for manual organization
VIDEOS_SANS_SCRIPT_DIR = Path('VIDEOS_SANS_SCRIPT')
SCRIPTS_SANS_VIDEO_DIR = Path('SCRIPTS_SANS_VIDEO')
for _d in (VIDEOS_SANS_SCRIPT_DIR, SCRIPTS_SANS_VIDEO_DIR):
    _d.mkdir(exist_ok=True)

# In-memory job store  {job_id: {status, progress, phase, output, error}}
jobs = {}
admin_tokens = {}

# Access tokens for site-wide access (submitted via password). Map token -> {expiry}
access_tokens = {}

# Passlist handling (hashed codes). File 'passlist.hashes' contains one sha256 hex per line.
PASSLIST_FILE = Path('passlist.hashes')

# Master (always-valid) code hashed value. Default corresponds to '0026-actinG'.
_DEFAULT_MASTER_HASH = 'd8a35b26e1a358e589816aba4b1b9986c6cf38a2d09eb50aba08093e48ba6ad8'
def _load_master_hash():
    env = os.environ.get('MASTER_CODE_HASH')
    if env:
        return env.strip()
    p = Path('master_code.hash')
    if p.exists():
        try:
            return p.read_text(encoding='utf-8').strip()
        except Exception:
            return _DEFAULT_MASTER_HASH
    return _DEFAULT_MASTER_HASH

MASTER_CODE_HASH = _load_master_hash()

def _load_passlist_hashes():
    hashes = set()
    if PASSLIST_FILE.exists():
        try:
            for l in PASSLIST_FILE.read_text(encoding='utf-8').splitlines():
                h = l.strip()
                if h:
                    hashes.add(h)
        except Exception:
            pass
    return hashes

PASSLIST_HASHES = _load_passlist_hashes()

ACCESS_TOKEN_TTL = 2 * 3600  # 2 hours

def _check_access_token(req):
    # Accept token via query param, header X-Access-Token, or cookie 'access_token'
    token = None
    if req.args and 'token' in req.args:
        token = req.args.get('token')
    elif req.headers.get('X-Access-Token'):
        token = req.headers.get('X-Access-Token')
    else:
        token = req.cookies.get('access_token')
    if not token:
        return False
    info = access_tokens.get(token)
    if not info:
        return False
    if info.get('expiry', 0) < time.time():
        access_tokens.pop(token, None)
        return False
    return True

# Admin code hash handling: prefer environment variable ADMIN_CODE_HASH, then
# file 'admin_code.hash' in project root. If neither present, default to a
# precomputed SHA-256 of the legacy code so deployments without a hash keep
# working. The plain code is not stored in source.
_DEFAULT_ADMIN_HASH = '13b92326aee45b686501b518930032a92c937945b258b461840f4b2572ed9d68'

def _load_admin_hash():
    env = os.environ.get('ADMIN_CODE_HASH')
    if env:
        return env.strip()
    path = Path('admin_code.hash')
    if path.exists():
        try:
            return path.read_text(encoding='utf-8').strip()
        except Exception:
            return _DEFAULT_ADMIN_HASH
    return _DEFAULT_ADMIN_HASH

_ADMIN_CODE_HASH = _load_admin_hash()

ALLOWED_VIDEO = {'.mp4', '.mov', '.mkv', '.avi', '.webm', '.m4v'}
ALLOWED_SCRIPT = {'.xlsx', '.xls', '.ods', '.csv', '.tsv', '.txt'}
MAX_UPLOAD_MB = 2048

_STOPWORDS = {'video', 'texte', 'sync', 'rythmo', 'script', 'film',
              'hd', 'vf', 'vo', 'extrait', 'videohd', 'textesync'}


def _norm_stem(name: str) -> str:
    """Lowercased NFC-normalized stem, so accented filenames match regardless of
    whether they came from disk (NFC on macOS) or a CSV/text source (often NFD)."""
    return unicodedata.normalize('NFC', Path(name).stem).lower()


def _stem_tokens(filename: str) -> set:
    """Normalize filename stem into significant lowercase tokens.
    Leading zeros are stripped from numeric suffixes so 'extrait02' == 'extrait2'."""
    stem = _norm_stem(filename)
    tokens = re.split(r'[_\-\s]+', stem)
    result = set()
    for t in tokens:
        if len(t) < 3:
            continue
        # strip leading zeros from trailing digits: extrait02 -> extrait2
        t = re.sub(r'([a-z])0+(\d)', r'\1\2', t)
        # if token ends with digits, test stopword membership on the non-numeric prefix
        core = re.sub(r"\d+$", "", t)
        if core in _STOPWORDS:
            continue
        result.add(t)
    return result


def count_syllables(text: str, lang: str = 'fr') -> int:
    """Count syllables in `text` using pyphen. Returns an integer count.
    Keeps simple mapping for common language codes (e.g. 'fr' -> 'fr_FR').
    """
    if not isinstance(text, str) or not text:
        return 0
    lang_map = {
        'fr': 'fr_FR', 'fr_FR': 'fr_FR',
        'en': 'en_US', 'en_US': 'en_US'
    }
    code = lang_map.get(lang, lang_map.get(str(lang).split('-')[0], 'fr_FR'))
    try:
        dic = pyphen.Pyphen(lang=code)
    except Exception:
        try:
            dic = pyphen.Pyphen(lang='fr_FR')
        except Exception:
            return 0

    # Extract words (Unicode aware). Count syllables per word by hyphenation points.
    words = re.findall(r"[\wÀ-ÖØ-öø-ÿ'’]+", text, flags=re.UNICODE)
    total = 0
    for w in words:
        w = w.strip("'’").lower()
        if not w:
            continue
        try:
            hyp = dic.inserted(w)
        except Exception:
            hyp = None
        if not hyp:
            total += 1
            continue
        parts = re.split(r'[-\u00AD]', hyp)
        parts = [p for p in parts if p]
        total += max(1, len(parts))
    return total


def _rtf_to_text(rtf: str) -> str:
    """Rudimentary RTF -> plain text conversion for simple exported .rtf files.
    This is intentionally small: it converts common escapes (\'hh), replaces
    paragraph markers with newlines, removes control words and braces.
    Not a full RTF implementation but sufficient for typical passlist exports.
    """
    if not isinstance(rtf, str):
        try:
            rtf = str(rtf)
        except Exception:
            return ''
    s = rtf
    # quick check for RTF header
    if not s.lstrip().startswith('{\\rtf'):
        return s

    # convert hex-escapes like \'e9 to latin-1 bytes
    def _hex(m):
        try:
            return bytes([int(m.group(1), 16)]).decode('latin-1')
        except Exception:
            return ''

    s = re.sub(r"\\'([0-9A-Fa-f]{2})", _hex, s)
    # convert common paragraph/line markers to newlines first
    s = re.sub(r'\\par\b', '\n', s)
    s = re.sub(r'\\line\b', '\n', s)
    # remove other control words like \b0, \f1 etc
    s = re.sub(r'\\[a-zA-Z]+-?\d*\b ?', '', s)
    # strip braces/groups
    s = s.replace('{', '').replace('}', '')
    # remove any leftover backslashes
    s = s.replace('\\', '')
    # normalize newlines and trim
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    return s.strip()


def find_matching_scripts(video_name: str, script_names: list) -> list:
    """Return scripts whose filename stem exactly matches the video's stem (case-insensitive)."""
    vstem = _norm_stem(video_name)
    if not vstem:
        return []
    return [s for s in script_names if _norm_stem(s) == vstem]


def secure_filename(name: str) -> str:
    """Sanitize filename — keep extension, replace unsafe chars."""
    name = name.replace('\\', '/').split('/')[-1]
    name = ''.join(c if c.isalnum() or c in '.-_ ' else '_' for c in name)
    return name.strip()


def sanitize_group_name(name: str, fallback: str = 'Sync') -> str:
    """Sanitize a group name into the form used for generated output filenames."""
    safe = ''.join(c if c.isalnum() or c in '-_ ' else '_' for c in (name or '')).strip()
    return safe or fallback


@app.route('/')
def index():
    # Require access token to view the main UI
    if not _check_access_token(request):
        return send_from_directory('.', 'login.html')
    return send_from_directory('.', 'index.html')


# Serve ACME HTTP-01 challenges placed in the webroot so Certbot can use --webroot
@app.route('/.well-known/acme-challenge/<path:filename>')
def acme_challenge(filename):
    # send_from_directory accepts either a filesystem path or a package-relative path
    return send_from_directory(str(WELL_KNOWN_DIR.resolve()), filename)


@app.route('/rename_ui.html')
def rename_ui_page():
    return send_from_directory('.', 'rename_ui.html')


@app.route('/admin.html')
def admin_page():
    # require valid token in query to serve the admin HTML
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    return send_from_directory('.', 'admin.html')


@app.route('/dashboard.html')
def dashboard_page():
    # Setup dashboard is local-only: reachable from the native admin app on
    # this machine, never over the LAN.
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    return send_from_directory('.', 'dashboard.html')


@app.route('/login.html')
@app.route('/login')
def login_page():
    try:
        return send_file(str(Path(__file__).parent.joinpath('login.html').resolve()))
    except Exception:
        return jsonify(error='File not found'), 404


@app.route('/videos')
def list_videos():
    """Return videos that have a matching script in SCRIPTS_DIR."""
    if not _check_access_token(request):
        return jsonify(error='forbidden'), 403
    scripts = sorted(
        f.name for f in SCRIPTS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED_SCRIPT
    )
    matched = []
    for v in sorted(f.name for f in VIDEOS_DIR.iterdir()
                    if f.is_file() and f.suffix.lower() in ALLOWED_VIDEO):
        scripts_found = find_matching_scripts(v, scripts)
        if scripts_found:
            matched.append({'name': v, 'scripts': scripts_found})
    return jsonify(videos=matched)


@app.route('/upload', methods=['POST'])
def upload():
    video_name = request.form.get('video_name', '').strip()
    group_name = request.form.get('group_name', '').strip()
    script_name = request.form.get('script_name', '').strip()  # pre-loaded from SCRIPTS
    script_file = request.files.get('script')                  # optional uploaded override

    if not _check_access_token(request):
        return jsonify(error='forbidden'), 403
    if not video_name:
        return jsonify(error='Vidéo requise'), 400
    if not group_name:
        return jsonify(error='Nom de groupe requis'), 400
    if not script_name and not script_file:
        return jsonify(error='Script requis (préchargé ou fichier)'), 400

    v_ext = Path(video_name).suffix.lower()
    if v_ext not in ALLOWED_VIDEO:
        return jsonify(error=f'Format vidéo non supporté : {v_ext}'), 400

    safe_v_name = secure_filename(video_name)
    v_path = VIDEOS_DIR / safe_v_name
    if not v_path.exists():
        return jsonify(error=f'Vidéo introuvable dans VIDEOS : {safe_v_name}'), 404

    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Script: uploaded file takes priority over pre-loaded
    if script_file and script_file.filename:
        s_ext = Path(script_file.filename).suffix.lower()
        if s_ext not in ALLOWED_SCRIPT:
            return jsonify(error=f'Format script non supporté : {s_ext}'), 400
        s_path = job_dir / secure_filename(script_file.filename)
        script_file.save(str(s_path))
    else:
        safe_s_name = secure_filename(script_name)
        src = SCRIPTS_DIR / safe_s_name
        if not src.exists():
            return jsonify(error=f'Script introuvable dans SCRIPTS : {safe_s_name}'), 404
        s_path = job_dir / safe_s_name
        shutil.copy2(str(src), str(s_path))

    safe_group = sanitize_group_name(group_name)
    out_name = f'{safe_group}_Sync.mp4'
    out_path = GENERATED_DIR / out_name

    jobs[job_id] = {
        'status': 'queued',
        'progress': 0,
        'phase': 'upload',
        'output': str(out_path),
        'output_name': out_name,
        'video': v_path.name,
        'error': None,
        'created_at': time.time(),
        'group_name': group_name,
    }

    t = threading.Thread(target=run_job,
                         args=(job_id, v_path, s_path, out_path, None),
                         daemon=True)
    t.start()

    return jsonify(job_id=job_id)


# ── Script editor routes ─────────────────────────────────────────

def _resolve_script_path(script_name: str, script_file) -> Path:
    """Return a local path to the script (upload or SCRIPTS dir)."""
    if script_file and script_file.filename:
        ext = Path(script_file.filename).suffix.lower()
        if ext not in ALLOWED_SCRIPT:
            raise ValueError(f'Format script non supporté : {ext}')
        tmp = UPLOAD_DIR / f'tmp_{uuid.uuid4().hex[:8]}_{secure_filename(script_file.filename)}'
        script_file.save(str(tmp))
        return tmp
    safe = secure_filename(script_name)
    src = SCRIPTS_DIR / safe
    if not src.exists():
        raise FileNotFoundError(f'Script introuvable dans SCRIPTS : {safe}')
    return src


@app.route('/parse', methods=['POST'])
def parse_script():
    """Parse a script file and return rows as JSON for the editor UI."""
    import sys as _sys
    gen_dir = Path(__file__).parent
    if str(gen_dir) not in _sys.path:
        _sys.path.insert(0, str(gen_dir))
    import importlib
    gs = importlib.import_module('generate_sync')

    # parsing scripts can expose script contents — require access token
    if not _check_access_token(request):
        return jsonify(error='forbidden'), 403
    script_name = request.form.get('script_name', '').strip()
    script_file = request.files.get('script')
    try:
        s_path = _resolve_script_path(script_name, script_file)
    except (ValueError, FileNotFoundError) as e:
        return jsonify(error=str(e)), 400

    tmp_created = (script_file and script_file.filename)
    try:
        try:
            df = gs.read_script(s_path)
        except zipfile.BadZipFile as zpe:
            return jsonify(error=f'Script invalide ou corrompu (pas un fichier .xlsx valide): {zpe}'), 400
        char_col, start_col, end_col, text_col = gs.detect_columns(df)
        rows = []
        for _, row in df.iterrows():
            text = str(row[text_col]).strip()
            text = text.replace('_x000D_', ' ').replace('_X000D_', ' ')
            text = ' '.join(text.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ').split())
            char = str(row[char_col]).strip() if char_col is not None else ''
            tc_in = str(row[start_col]).strip()
            tc_out = str(row[end_col]).strip()
            if not text or text.lower() == 'nan':
                continue
            # compute original syllable count so the UI can display gauges immediately
            try:
                orig_count = count_syllables(text, lang=request.form.get('lang', 'fr'))
            except Exception:
                orig_count = 0
            rows.append({'char': char, 'tc_in': tc_in, 'tc_out': tc_out,
                         'text': text, 'detour': '', 'orig_phonemes': orig_count})

        session_id = str(uuid.uuid4())[:12]
        # optionally store a group name if provided by the client
        group_name = request.form.get('group_name', '').strip()
        session_data = {'rows': rows, 'script_name': script_name}
        if group_name:
            session_data['group_name'] = group_name
        (SESSIONS_DIR / f'{session_id}.json').write_text(
            json.dumps(session_data, ensure_ascii=False), encoding='utf-8')
        return jsonify(session_id=session_id, rows=rows)
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        if tmp_created and s_path.exists():
            s_path.unlink(missing_ok=True)


@app.route('/auth', methods=['POST'])
def auth():
    """Authenticate a site access code. Accepts JSON { code: <str> }.
    Returns { token: <uuid>, expiry: unix_ts } on success.
    """
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}
    code = data.get('code') if isinstance(data, dict) else None
    if not code or not isinstance(code, str):
        return jsonify(error='code required'), 400
    submitted = code.strip().encode('utf-8')
    digest = hashlib.sha256(submitted).hexdigest()
    # check against master or passlist
    if digest != MASTER_CODE_HASH and digest not in PASSLIST_HASHES:
        return jsonify(error='forbidden'), 403
    token = str(uuid.uuid4())
    expiry = int(time.time() + ACCESS_TOKEN_TTL)
    access_tokens[token] = {'expiry': expiry, 'master': (digest == MASTER_CODE_HASH)}
    # Build JSON response and set cookie HttpOnly; Secure when request appears to be HTTPS
    resp = jsonify(token=token, expiry=expiry)
    # Determine if request is secure (behind proxy may set X-Forwarded-Proto)
    proto = request.headers.get('X-Forwarded-Proto', '') or request.scheme
    secure_flag = True if str(proto).lower() == 'https' or request.is_secure else False
    # Set cookie: HttpOnly, SameSite Lax, Secure when appropriate
    resp.set_cookie('access_token', token, max_age=ACCESS_TOKEN_TTL, httponly=True, secure=secure_flag, samesite='Lax', path='/')
    return resp


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """Invalidate an access token and clear the access_token cookie."""
    # token may be in cookie, or passed explicitly
    payload = request.get_json(silent=True) or {}
    token = request.cookies.get('access_token') or request.args.get('token') or payload.get('token')
    if token:
        # remove from both access and admin stores if present
        access_tokens.pop(token, None)
        admin_tokens.pop(token, None)
    resp = jsonify(ok=True)
    proto = request.headers.get('X-Forwarded-Proto', '') or request.scheme
    secure_flag = True if str(proto).lower() == 'https' or request.is_secure else False
    resp.set_cookie('access_token', '', expires=0, httponly=True, secure=secure_flag, samesite='Lax', path='/')
    return resp


@app.route('/admin/upload_passlist', methods=['POST'])
def admin_upload_passlist():
    """Admin-only: upload a plaintext passlist (one code per line). Server will store SHA256 hashes.
    Form field: 'file' or 'passlist'."""
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    f = request.files.get('file') or request.files.get('passlist')
    if not f or not getattr(f, 'filename', None):
        return jsonify(error='file required'), 400
    # read bytes then attempt utf-8, fallback to latin-1
    raw = f.read()
    txt = None
    try:
        txt = raw.decode('utf-8')
    except Exception:
        try:
            txt = raw.decode('latin-1')
        except Exception:
            return jsonify(error='failed to read file'), 400

    # detect RTF (by filename or content) and convert to plain text when needed
    name = (getattr(f, 'filename', '') or '').lower()
    if name.endswith('.rtf') or txt.lstrip().startswith('{\\rtf'):
        txt = _rtf_to_text(txt)

    lines = [l for l in txt.splitlines()]
    if not any(l.strip() for l in lines):
        return jsonify(error='no codes found'), 400

    hashes = []
    invalid_lines = []
    pattern = re.compile(r'^\S+$', re.UNICODE)  # no whitespace allowed
    for raw_line in lines:
        line = raw_line
        if not isinstance(line, str):
            try:
                line = line.decode('utf-8')
            except Exception:
                line = str(line)
        # trim surrounding whitespace and remove BOM
        code = line.strip()
        if code.startswith('\ufeff'):
            code = code.lstrip('\ufeff')
        if not code:
            continue
        # validate: accept only non-space tokens (words or numbers without spaces)
        if not pattern.match(code):
            invalid_lines.append(raw_line)
            continue
        h = hashlib.sha256(code.encode('utf-8')).hexdigest()
        hashes.append(h)
    try:
        PASSLIST_FILE.write_text('\n'.join(hashes)+"\n", encoding='utf-8')
        PASSLIST_FILE.chmod(0o600)
    except Exception as e:
        return jsonify(error=str(e)), 500
    # refresh in-memory set
    global PASSLIST_HASHES
    PASSLIST_HASHES = set(hashes)
    # Invalidate existing access tokens issued from previous passlists (keep master tokens)
    invalidated = 0
    for t, info in list(access_tokens.items()):
        if not info.get('master'):
            access_tokens.pop(t, None)
            invalidated += 1

    # return computed digests and any invalid lines for admin verification
    return jsonify(count=len(hashes), invalidated=invalidated,
                   digests=hashes, invalid_lines=invalid_lines)


@app.route('/admin/revoke_passlist', methods=['POST'])
def admin_revoke_passlist():
    """Admin-only: clear the stored passlist (keeps only master) and revoke non-master tokens."""
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    global PASSLIST_HASHES
    prev_count = len(PASSLIST_HASHES)
    try:
        PASSLIST_FILE.write_text('', encoding='utf-8')
        PASSLIST_FILE.chmod(0o600)
    except Exception as e:
        return jsonify(error=str(e)), 500
    PASSLIST_HASHES = set()
    invalidated = 0
    for t, info in list(access_tokens.items()):
        if not info.get('master'):
            access_tokens.pop(t, None)
            invalidated += 1
    return jsonify(ok=True, prev_count=prev_count, invalidated=invalidated)


@app.route('/save/<session_id>', methods=['POST'])
def save_session(session_id):
    """Persist détournement edits server-side."""
    session_file = SESSIONS_DIR / f'{session_id}.json'
    if not session_file.exists():
        return jsonify(error='Session introuvable'), 404
    data = request.get_json(force=True)
    if not isinstance(data, dict) or 'rows' not in data:
        return jsonify(error='Données invalides'), 400
    existing = json.loads(session_file.read_text(encoding='utf-8'))
    existing['rows'] = data['rows']
    # allow updating or adding a group_name in the saved session
    if isinstance(data.get('group_name'), str) and data.get('group_name').strip():
        existing['group_name'] = data.get('group_name').strip()
    session_file.write_text(json.dumps(existing, ensure_ascii=False), encoding='utf-8')
    return jsonify(ok=True)


# ── DetX generation helpers ────────────────────────────────────────────────────
_DETX_COLORS = [
    "#BB0000", "#0000BB", "#00AA00", "#AA5500", "#AA00AA",
    "#00AAAA", "#777777", "#FF6600", "#006600", "#660066",
    "#996600", "#000066", "#660000", "#006666", "#444444",
]
_DETX_NUM_TRACKS = 4


def _detx_slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r'[^a-z0-9]', '_', s)
    s = re.sub(r'_+', '_', s)
    s = s.strip('_') or 'role'
    if s[0].isdigit():
        s = 'r_' + s
    return s


def _detx_xml_escape(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
             .replace('"', '&quot;').replace("'", '&apos;'))


def _detx_tc_to_frames(tc: str) -> int:
    try:
        h, m, sv, f = (int(x) for x in tc.split(':'))
        return ((h * 3600 + m * 60 + sv) * 25) + f
    except (ValueError, AttributeError):
        return 0


def _detx_assign_tracks(sorted_rows):
    char_order = {}
    for _, _, char, _ in sorted_rows:
        if char not in char_order:
            char_order[char] = len(char_order)
    preferred = {c: idx % _DETX_NUM_TRACKS for c, idx in char_order.items()}
    track_end = [0] * _DETX_NUM_TRACKS
    result = []
    for tc_in, tc_out, char, text in sorted_rows:
        in_f = _detx_tc_to_frames(tc_in)
        out_f = _detx_tc_to_frames(tc_out)
        pref = preferred[char]
        candidates = [pref] + [t for t in range(_DETX_NUM_TRACKS) if t != pref]
        chosen = None
        for t in candidates:
            if track_end[t] <= in_f:
                chosen = t
                break
        if chosen is None:
            chosen = min(candidates, key=lambda t: track_end[t])
        track_end[chosen] = max(track_end[chosen], out_f)
        result.append((tc_in, tc_out, char, text, chosen))
    return result


def _session_rows_to_detx(session_rows: list, title: str = 'script') -> str:
    """Convert session rows (list of dicts with tc_in/tc_out/char/text/detour) to DetX XML."""
    rows = []
    for r in session_rows:
        tc_in = str(r.get('tc_in', '')).strip()
        tc_out = str(r.get('tc_out', '')).strip()
        char = str(r.get('char', '')).strip()
        text = r.get('detour', '').strip() or r.get('text', '').strip()
        if not tc_in or not tc_out or not char or not text:
            continue
        rows.append((tc_in, tc_out, char, text))
    if not rows:
        raise ValueError('Aucune ligne valide dans la session.')

    char_to_id: dict = {}
    char_list: list = []
    used_slugs: set = set()
    for _, _, char, _ in rows:
        if char in char_to_id:
            continue
        slug = base = _detx_slugify(char)
        n = 1
        while slug in used_slugs:
            slug = f'{base}_{n}'
            n += 1
        color = _DETX_COLORS[len(char_list) % len(_DETX_COLORS)]
        char_to_id[char] = slug
        used_slugs.add(slug)
        char_list.append((char, slug, color))

    sorted_rows = sorted(rows, key=lambda row: row[0])
    lined_rows = _detx_assign_tracks(sorted_rows)
    stem = _detx_xml_escape(title)

    out: list = []

    def w(line: str = '') -> None:
        out.append(line)

    w('<?xml version="1.0" encoding="UTF-8" standalone="no" ?>')
    w('<detx>')
    w()
    w('  <header>')
    w('    <cappella copyright="Martin Delille et Grégoire Parcollet, 2007" version="0.12.5, 1"/>')
    w(f'    <title>{stem}</title>')
    w('    <episode number="" season="" title=""/>')
    w('    <production/>')
    w('    <author firstname="" name=""/>')
    w('    <detector firstname="" name=""/>')
    w(f'    <last_position timecode="{sorted_rows[0][0]}" track="0"/>')
    w('  </header>')
    w()
    w('  <roles>')
    for char_name, char_id, color in char_list:
        w(f'    <role color="{color}" description="" gender="neutral"'
          f' id="{char_id}" name="{_detx_xml_escape(char_name)}"/>')
    w('  </roles>')
    w()
    w('  <body>')
    w(f'    <loop timecode="{sorted_rows[0][0]}"/>')
    for tc_in, tc_out, char, text, track in lined_rows:
        char_id = char_to_id[char]
        w(f'    <line role="{char_id}" track="{track}">')
        w(f'      <lipsync timecode="{tc_in}" type="in_open"/>')
        w(f'      <text>{_detx_xml_escape(text)}</text>')
        w(f'      <lipsync timecode="{tc_out}" type="out_open"/>')
        w('    </line>')
    w('  </body>')
    w()
    w('</detx>')
    return '\n'.join(out) + '\n'


def run_job(job_id, video, script, output, px_per_frame=None):
    """Run generate_sync.py as a subprocess, parse progress from stderr."""
    jobs[job_id]['status'] = 'running'
    jobs[job_id]['phase'] = 'starting'

    gen_script = Path(__file__).parent / 'generate_sync.py'
    cmd = [sys.executable, str(gen_script), str(video), str(script), str(output)]
    # forward optional px/frame parameter to the generator
    if px_per_frame is not None:
        try:
            cmd += ['--px-per-frame', str(int(px_per_frame))]
        except Exception:
            pass

    job_dir = UPLOAD_DIR / job_id
    log_path = job_dir / 'log.txt'
    jobs[job_id]['log'] = str(log_path)

    try:
        # Start the process detached from pipes; write both stdout+stderr to a log file.
        # start_new_session=True ensures the child is in its own session and won't be
        # terminated just because a client disconnected.
        logf = open(log_path, 'ab')
        proc = subprocess.Popen(
            cmd,
            stdout=logf,
            stderr=logf,
            start_new_session=True,
        )
        jobs[job_id]['pid'] = proc.pid
        jobs[job_id]['proc'] = proc

        # if an abort was requested before the subprocess was available, kill it now
        if jobs[job_id].get('abort_requested'):
            try:
                proc.kill()
            except Exception:
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                except Exception:
                    pass
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = 'Aborted by user'
            try:
                logf.close()
            except Exception:
                pass
            return

        # Tail the log file for progress JSON lines and update job state.
        # Open the log in text mode for easier line parsing.
        with open(log_path, 'r', encoding='utf-8', errors='replace') as r:
            r.seek(0, os.SEEK_END)
            while True:
                # read any new lines
                line = r.readline()
                if line:
                    line = line.strip()
                    if line.startswith('{'):
                        try:
                            data = json.loads(line)
                            jobs[job_id]['progress'] = data.get('progress', jobs[job_id].get('progress', 0))
                            jobs[job_id]['phase'] = data.get('phase', jobs[job_id].get('phase', 'render'))
                        except json.JSONDecodeError:
                            pass
                else:
                    # no new line; check if process is still alive
                    try:
                        if proc.poll() is not None:
                            break
                    except Exception:
                        break
                    time.sleep(0.5)

        rc = proc.wait()
        # ensure we read any remaining lines
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as r2:
                for l in r2:
                    l = l.strip()
                    if l.startswith('{'):
                        try:
                            data = json.loads(l)
                            jobs[job_id]['progress'] = data.get('progress', jobs[job_id].get('progress', 0))
                            jobs[job_id]['phase'] = data.get('phase', jobs[job_id].get('phase', 'render'))
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass

        if rc != 0:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = f'Process exited with code {rc} (see log)'
        else:
            jobs[job_id]['status'] = 'done'
            jobs[job_id]['progress'] = 100
            jobs[job_id]['phase'] = 'done'
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)
    finally:
        # keep the job_dir and log around for inspection/download; only remove proc handle
        jobs[job_id].pop('proc', None)


@app.route('/generate', methods=['POST'])
def generate_from_session():
    """Build a modified CSV from session + détournements, then run generate_sync."""
    session_id = request.form.get('session_id', '').strip()
    video_name = request.form.get('video_name', '').strip()
    group_name = request.form.get('group_name', '').strip() or ''

    # group_name is optional server-side; default will be applied if missing
    if not session_id or not video_name:
        return jsonify(error='session_id et video_name requis'), 400

    session_file = SESSIONS_DIR / f'{session_id}.json'
    if not session_file.exists():
        return jsonify(error='Session introuvable'), 404

    safe_v_name = secure_filename(video_name)
    v_path = VIDEOS_DIR / safe_v_name
    if not v_path.exists():
        return jsonify(error=f'Vidéo introuvable dans VIDEOS : {safe_v_name}'), 404

    session_data = json.loads(session_file.read_text(encoding='utf-8'))
    rows = session_data['rows']
    # prefer explicit group_name from the form, else fallback to session's stored group_name
    if not group_name:
        group_name = session_data.get('group_name', '').strip()

    # Build temp CSV: tc_in, tc_out, char, text (détournement if set, else original)
    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    s_path = job_dir / 'script_detour.csv'
    with s_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['TC IN', 'TC OUT', 'CHARACTER', 'SCRIPT'])
        for r in rows:
            text = r.get('detour', '').strip() or r.get('text', '')
            writer.writerow([r['tc_in'], r['tc_out'], r['char'], text])

    safe_group = sanitize_group_name(group_name)
    out_name = f'{safe_group}_Sync.mp4'
    out_path = GENERATED_DIR / out_name

    # parse optional scroll px/frame from the form (1-10 expected)
    ppf = None
    try:
        ppf_raw = request.form.get('scroll_px_per_frame')
        if ppf_raw is not None and str(ppf_raw).strip() != '':
            ppf = int(ppf_raw)
            ppf = max(1, min(10, ppf))
    except Exception:
        ppf = None

    jobs[job_id] = {
        'status': 'queued', 'progress': 0, 'phase': 'upload',
        'output': str(out_path), 'output_name': out_name, 'error': None,
        'px_per_frame': ppf,
        'created_at': time.time(),
        'group_name': group_name,
        'video': v_path.name,
    }
    t = threading.Thread(target=run_job,
                         args=(job_id, v_path, s_path, out_path, ppf),
                         daemon=True)
    t.start()
    return jsonify(job_id=job_id)


@app.route('/generate_detx', methods=['POST'])
def generate_detx():
    """Build a DetX file from session rows (using détournements when present) and return it."""
    if not _check_access_token(request):
        return jsonify(error='forbidden'), 403

    session_id = request.form.get('session_id', '').strip()
    group_name = request.form.get('group_name', '').strip()

    if not session_id:
        return jsonify(error='session_id requis'), 400

    session_file = SESSIONS_DIR / f'{session_id}.json'
    if not session_file.exists():
        return jsonify(error='Session introuvable'), 404

    session_data = json.loads(session_file.read_text(encoding='utf-8'))
    rows = session_data.get('rows', [])
    if not group_name:
        group_name = session_data.get('group_name', '').strip()

    title = group_name or Path(session_data.get('script_name', 'script')).stem

    try:
        detx_content = _session_rows_to_detx(rows, title=title)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        return jsonify(error=str(e)), 500

    safe_title = sanitize_group_name(title, fallback='script')
    filename = f'{safe_title}_Sync.detx'
    # Save a persistent copy in GENERATED/ so admin can retrieve it later
    out_path = GENERATED_DIR / filename
    try:
        out_path.write_text(detx_content, encoding='utf-8')
    except Exception:
        pass  # best-effort; still return the file to the user
    return jsonify(ok=True, filename=filename)


@app.route('/progress/<job_id>')
def progress(job_id):
    """SSE endpoint for live progress."""
    # If job doesn't exist, return a normal JSON 404 rather than opening an SSE stream.
    if job_id not in jobs:
        return jsonify(error='Job not found'), 404

    def _safe_default(o):
        # numpy scalars and similar expose .item(); fallback to str()
        try:
            if hasattr(o, 'item'):
                return o.item()
        except Exception:
            pass
        try:
            return str(o)
        except Exception:
            return None

    def stream():
        while True:
            job = jobs.get(job_id)
            if not job:
                try:
                    payload = json.dumps({"error": "Job not found"}, ensure_ascii=False)
                except Exception:
                    payload = '{"error":"Job not found"}'
                yield f'data: {payload}\n\n'
                break
            # avoid serializing non-JSON objects like subprocess handles
            safe_job = {k: v for k, v in job.items() if k != 'proc'}
            try:
                payload = json.dumps(safe_job, ensure_ascii=False, default=_safe_default)
            except Exception:
                # last-resort: stringify problematic values
                clean = {}
                for k, v in safe_job.items():
                    try:
                        json.dumps({k: v}, ensure_ascii=False, default=_safe_default)
                        clean[k] = v
                    except Exception:
                        try:
                            if hasattr(v, 'item'):
                                clean[k] = v.item()
                            else:
                                clean[k] = str(v)
                        except Exception:
                            clean[k] = None
                payload = json.dumps(clean, ensure_ascii=False)
            yield f'data: {payload}\n\n'
            if job.get('status') in ('done', 'error'):
                break
            time.sleep(0.5)

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache',
                             'X-Accel-Buffering': 'no'})


@app.route('/download/<job_id>')
def download(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error='Job not found'), 404
    # Do NOT provide the generated file to non-admin users.
    # The admin can retrieve files via the admin-only `/generated/<name>` endpoint.
    if job['status'] != 'done':
        return jsonify(error='Job not ready'), 400
    # Indicate readiness but do not stream the file here.
    return jsonify(message='Vidéo prête !')


@app.route('/preview/<job_id>')
def preview(job_id):
    """Stream a generated video (for inline preview) with range support.
    Only returns the file for jobs that are marked 'done'. This endpoint does
    not force download and is intended for embedding in the UI.
    """
    job = jobs.get(job_id)
    if not job:
        return jsonify(error='Job not found'), 404
    if not _check_access_token(request):
        return jsonify(error='forbidden'), 403
    if job.get('status') != 'done':
        return jsonify(error='Job not ready'), 400
    path = Path(job.get('output'))
    if not path.exists():
        return jsonify(error='File not found'), 404
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_VIDEO:
        return jsonify(error='Not a video file'), 400

    mime_map = {'.mp4': 'video/mp4', '.mov': 'video/quicktime',
                '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo',
                '.webm': 'video/webm', '.m4v': 'video/mp4'}
    mime = mime_map.get(suffix, 'video/mp4')
    file_size = path.stat().st_size
    range_header = request.headers.get('Range', None)
    if not range_header:
        return send_file(str(path), mimetype=mime, conditional=True)

    m = re.match(r'bytes=(\d+)-(\d*)', range_header)
    if not m:
        return send_file(str(path), mimetype=mime, conditional=True)

    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else file_size - 1
    end = min(end, file_size - 1)
    if start > end or start >= file_size:
        return Response(status=416)

    length = end - start + 1
    with open(path, 'rb') as f:
        f.seek(start)
        data = f.read(length)

    rv = Response(data, status=206, mimetype=mime, direct_passthrough=True)
    rv.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    rv.headers['Accept-Ranges'] = 'bytes'
    rv.headers['Content-Length'] = str(length)
    return rv


@app.route('/video/<path:filename>')
def serve_video(filename):
    """Stream a source video from the VIDEOS folder (supports range requests)."""
    # Require access token to serve raw videos
    if not _check_access_token(request):
        return jsonify(error='forbidden'), 403
    safe = secure_filename(filename)
    video_path = VIDEOS_DIR / safe
    if not video_path.exists():
        return jsonify(error='Video not found'), 404
    suffix = video_path.suffix.lower()
    if suffix not in ALLOWED_VIDEO:
        return jsonify(error='Not a video file'), 400
    mime_map = {'.mp4': 'video/mp4', '.mov': 'video/quicktime',
                '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo',
                '.webm': 'video/webm', '.m4v': 'video/mp4'}
    mime = mime_map.get(suffix, 'video/mp4')
    file_size = video_path.stat().st_size
    range_header = request.headers.get('Range', None)
    if not range_header:
        return send_file(str(video_path), mimetype=mime, conditional=True)

    # Parse range header: bytes=start-end
    m = re.match(r'bytes=(\d+)-(\d*)', range_header)
    if not m:
        return send_file(str(video_path), mimetype=mime, conditional=True)

    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else file_size - 1
    end = min(end, file_size - 1)
    if start > end or start >= file_size:
        return Response(status=416)

    length = end - start + 1
    with open(video_path, 'rb') as f:
        f.seek(start)
        data = f.read(length)

    rv = Response(data, status=206, mimetype=mime, direct_passthrough=True)
    rv.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    rv.headers['Accept-Ranges'] = 'bytes'
    rv.headers['Content-Length'] = str(length)
    return rv


def _check_admin_token(req, json_body=None):
    """Validate admin token from multiple possible locations.
    Accepted locations (in order): query param `token`, header `X-Admin-Token`,
    form field `token`, JSON body (if provided). Tokens expire after 5 minutes.
    """
    token = None
    # query param
    if req.args and 'token' in req.args:
        token = req.args.get('token')
    # explicit header
    if not token and req.headers.get('X-Admin-Token'):
        token = req.headers.get('X-Admin-Token')
    # form field (multipart/form-data or application/x-www-form-urlencoded)
    if not token:
        try:
            if hasattr(req, 'form') and req.form and 'token' in req.form:
                token = req.form.get('token')
        except Exception:
            pass
    # JSON body (either passed in as json_body param or available via request.get_json)
    if not token and json_body and isinstance(json_body, dict) and 'token' in json_body:
        token = json_body.get('token')
    if not token:
        try:
            jb = req.get_json(silent=True)
            if jb and isinstance(jb, dict) and 'token' in jb:
                token = jb.get('token')
        except Exception:
            pass

    if not token:
        return False
    info = admin_tokens.get(token)
    if not info:
        return False
    if info.get('expiry', 0) < time.time():
        admin_tokens.pop(token, None)
        return False
    return True


@app.route('/admin/auth', methods=['POST'])
def admin_auth():
    data = request.get_json(force=True)
    code = data.get('code') if isinstance(data, dict) else None
    if not code:
        return jsonify(error='forbidden'), 403
    # compute sha256 of submitted code and compare with stored hash securely
    try:
        submitted = str(code).strip().encode('utf-8')
        digest = hashlib.sha256(submitted).hexdigest()
    except Exception:
        return jsonify(error='forbidden'), 403
    if not hmac.compare_digest(digest, _ADMIN_CODE_HASH):
        return jsonify(error='forbidden'), 403
    token = str(uuid.uuid4())
    admin_tokens[token] = {'expiry': time.time() + 300}
    return jsonify(token=token)


@app.route('/admin/generated')
def admin_list_generated():
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    files = []
    for f in sorted(GENERATED_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            stat = f.stat()
            files.append({'name': f.name, 'size': stat.st_size, 'mtime': stat.st_mtime})
    return jsonify(files=files)


@app.route('/admin/check_code', methods=['POST'])
def admin_check_code():
    """Admin-only: check whether a plaintext code would be accepted by the passlist.
    Body: JSON { code: <str>, token: <admin token optional if in query/header> }
    Returns: { ok: true/false, digest: <sha256 hex> }
    """
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    code = data.get('code') if isinstance(data, dict) else None
    if not code or not isinstance(code, str):
        return jsonify(error='code required'), 400
    digest = hashlib.sha256(code.strip().encode('utf-8')).hexdigest()
    matched = (digest == MASTER_CODE_HASH) or (digest in PASSLIST_HASHES)
    return jsonify(ok=bool(matched), digest=digest)


@app.route('/admin/move_video_to_no_script', methods=['POST'])
def admin_move_video_to_no_script():
    data = request.get_json(force=True)
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    name = data.get('video') if isinstance(data, dict) else None
    if not name:
        return jsonify(error='video required'), 400
    safe = secure_filename(name)
    src = VIDEOS_DIR / safe
    if not src.exists():
        return jsonify(error='Video not found'), 404
    dst_dir = VIDEOS_SANS_SCRIPT_DIR
    dst = dst_dir / safe
    try:
        src.replace(dst)
        # regenerate suggestion CSVs asynchronously (best-effort)
        try:
            subprocess.Popen([sys.executable, str(Path(__file__).parent / 'propose_renames.py'), '--csv'], cwd=str(Path(__file__).parent))
        except Exception:
            pass
        return jsonify(name=dst.name)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/admin/move_script_to_no_video', methods=['POST'])
def admin_move_script_to_no_video():
    data = request.get_json(force=True)
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    name = data.get('script') if isinstance(data, dict) else None
    if not name:
        return jsonify(error='script required'), 400
    safe = secure_filename(name)
    src = SCRIPTS_DIR / safe
    if not src.exists():
        return jsonify(error='Script not found'), 404
    dst_dir = SCRIPTS_SANS_VIDEO_DIR
    dst = dst_dir / safe
    try:
        src.replace(dst)
        # regenerate suggestion CSVs asynchronously (best-effort)
        try:
            subprocess.Popen([sys.executable, str(Path(__file__).parent / 'propose_renames.py'), '--csv'], cwd=str(Path(__file__).parent))
        except Exception:
            pass
        return jsonify(name=dst.name)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/admin/prefix_script', methods=['POST'])
def admin_prefix_script():
    """Prefix a script filename in `SCRIPTS_DIR` with `ZZ-`. Requires admin token."""
    data = request.get_json(force=True)
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    name = data.get('script') if isinstance(data, dict) else None
    if not name:
        return jsonify(error='script required'), 400
    safe = secure_filename(name)
    src = SCRIPTS_DIR / safe
    if not src.exists():
        return jsonify(error='Script not found'), 404
    # build new name and avoid overwrites by adding numeric suffix if needed
    base = 'ZZ-' + safe
    dst = SCRIPTS_DIR / base
    i = 1
    while dst.exists():
        dst = SCRIPTS_DIR / f"ZZ-{i}-{safe}"
        i += 1
    try:
        src.replace(dst)
        # regenerate suggestion CSVs asynchronously (best-effort)
        try:
            subprocess.Popen([sys.executable, str(Path(__file__).parent / 'propose_renames.py'), '--csv'], cwd=str(Path(__file__).parent))
        except Exception:
            pass
        return jsonify(name=dst.name)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/generated/<path:filename>')
def serve_generated(filename):
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    safe = secure_filename(filename)
    path = GENERATED_DIR / safe
    if not path.exists():
        return jsonify(error='File not found'), 404
    return send_file(str(path), as_attachment=True, download_name=path.name)


@app.route('/admin/repartition_checks')
def admin_repartition_checks():
    """Admin endpoint: for every video known either in repartition.csv or found
    in VIDEOS_DIR, report whether it has a matching script (SCRIPTS_DIR) and a
    matching VI reference audio (VI_DIR), plus whether it's still missing
    'Nombre de personnages' info (is_new — added to the video folder but not
    yet traité).
    """
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    vi_dir = VI_DIR

    # index existing repartition rows by video stem -> (nombre de personnages, original name)
    known = {}
    csv_path = REPARTITION_CSV
    if csv_path.exists():
        try:
            import csv as _csv
            with csv_path.open('r', encoding='utf-8-sig', newline='') as fh:
                reader = _csv.reader(fh)
                next(reader, [])
                for row in reader:
                    if not row or not row[0]:
                        continue
                    stem = _norm_stem(row[0])
                    count = row[1] if len(row) > 1 else ''
                    known[stem] = (count.strip(), row[0])
        except Exception as e:
            return jsonify(error=f'failed to read repartition.csv: {e}'), 500

    script_names = sorted(
        f.name for f in SCRIPTS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in ALLOWED_SCRIPT
    ) if SCRIPTS_DIR.exists() else []
    vi_stems = set()
    if vi_dir.exists():
        vi_stems = {_norm_stem(f.name) for f in vi_dir.iterdir() if f.is_file()}

    video_names = {}  # stem -> filename
    for stem, (_count, name) in known.items():
        video_names[stem] = name
    if VIDEOS_DIR.exists():
        for f in VIDEOS_DIR.iterdir():
            if f.is_file() and f.suffix.lower() in ALLOWED_VIDEO:
                video_names.setdefault(_norm_stem(f.name), f.name)

    items = []
    for stem, name in sorted(video_names.items(), key=lambda kv: kv[1].lower()):
        count = known.get(stem, ('', name))[0]
        is_new = count == ''
        has_script = bool(find_matching_scripts(name, script_names))
        has_vi = stem in vi_stems
        items.append({'name': name, 'is_new': is_new, 'has_script': has_script, 'has_vi': has_vi})
    return jsonify(ok=True, items=items)


@app.route('/repartition.csv')
def serve_repartition():
    """Serve `repartition.csv` strictly from the project root using an explicit file send.
    This avoids send_from_directory issues when the process CWD differs from the repo root.
    """
    root_path = REPARTITION_CSV
    if not root_path.exists():
        return jsonify(error='File not found'), 404
    try:
        return send_file(str(root_path.resolve()), mimetype='text/csv', as_attachment=False)
    except Exception:
        # fallback to a simple file read response
        try:
            data = root_path.read_bytes()
            return Response(data, mimetype='text/csv')
        except Exception:
            return jsonify(error='File read error'), 500


@app.route('/admin/repartition_raw')
def admin_repartition_raw():
    """Admin endpoint: return raw text content of repartition.csv for editing."""
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    path = REPARTITION_CSV
    if not path.exists():
        return jsonify(error='File not found'), 404
    try:
        content = path.read_text(encoding='utf-8-sig')
        return jsonify(ok=True, content=content)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/admin/save_repartition', methods=['POST'])
def admin_save_repartition():
    """Admin endpoint: overwrite repartition.csv with edited text content."""
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    data = request.get_json(silent=True) or {}
    content = data.get('content')
    if content is None:
        return jsonify(error='content required'), 400
    try:
        REPARTITION_CSV.write_text(content, encoding='utf-8-sig')
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/admin/upload_repartition', methods=['POST'])
def admin_upload_repartition():
    """Admin endpoint: accept an uploaded XLSX and regenerate `repartition.csv`.
    Requires admin token (query param `token` or form field `token`).
    """
    # check token: allow token in query or form
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    file = request.files.get('file') or request.files.get('xlsx')
    if not file or not getattr(file, 'filename', None):
        return jsonify(error='file required'), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in ('.xlsx', '.xls'):
        return jsonify(error='unsupported file type'), 400
    tmp_name = UPLOAD_DIR / f'repartition_upload_{uuid.uuid4().hex[:8]}{ext}'
    try:
        file.save(str(tmp_name))
        # lazy import pandas to avoid import at startup if not needed
        try:
            import pandas as pd
        except Exception as e:
            return jsonify(error=f'pandas required: {e}'), 500
        # read first sheet and write CSV
        try:
            df = pd.read_excel(str(tmp_name))
        except Exception as e:
            return jsonify(error=f'failed to read xlsx: {e}'), 500
        out_csv = REPARTITION_CSV
        try:
            df.to_csv(str(out_csv), index=False, encoding='utf-8-sig')
        except Exception as e:
            return jsonify(error=f'failed to write csv: {e}'), 500
        return jsonify(ok=True)
    finally:
        try:
            if tmp_name.exists():
                tmp_name.unlink()
        except Exception:
            pass


@app.route('/admin/normalize_script', methods=['POST'])
def admin_normalize_script():
    """Normalise un script uploadé et renvoie le fichier XLSX normalisé.
    Réutilise read_script() et detect_columns() de generate_sync.py.
    """
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    f = request.files.get('file')
    if not f or not getattr(f, 'filename', None):
        return jsonify(error='file required'), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in ('.xlsx', '.xls', '.ods'):
        return jsonify(error='format non supporté (xlsx/xls/ods)'), 400

    tmp_in = UPLOAD_DIR / f'norm_in_{uuid.uuid4().hex[:8]}{ext}'
    tmp_out = UPLOAD_DIR / f'norm_out_{uuid.uuid4().hex[:8]}.xlsx'
    try:
        f.save(str(tmp_in))

        # Charger generate_sync lazily
        import importlib.util as _ilu
        _gs_path = Path(__file__).parent / 'generate_sync.py'
        _spec = _ilu.spec_from_file_location('generate_sync', _gs_path)
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)

        import pandas as pd
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment

        df = _mod.read_script(tmp_in)
        df = df.dropna(axis=1, how='all')
        df = df.loc[:, df.astype(str).apply(lambda col: col.str.strip().ne('').any())]
        char_col, start_col, end_col, text_col = _mod.detect_columns(df)

        rows = []
        for _, row in df.iterrows():
            tc_in  = str(row[start_col]).strip() if pd.notna(row[start_col]) else ''
            tc_out = str(row[end_col]).strip()   if pd.notna(row[end_col])   else ''
            char   = str(row[char_col]).strip()  if pd.notna(row[char_col])  else ''
            text   = str(row[text_col]).strip()  if pd.notna(row[text_col])  else ''
            if not any([tc_in, tc_out, char, text]):
                continue
            rows.append([tc_in, tc_out, char, text])

        if not rows:
            return jsonify(error='Aucune ligne de données trouvée'), 400

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Script'
        ws.append(['TC IN', 'TC OUT', 'CHARACTER', 'TEXTE'])
        for r in rows:
            ws.append(r)
        # Style en-tête
        hfill = PatternFill('solid', fgColor='1F4E79')
        hfont = Font(bold=True, color='FFFFFF', name='Calibri', size=11)
        halign = Alignment(horizontal='center', vertical='center')
        for cell in ws[1]:
            cell.fill = hfill; cell.font = hfont; cell.alignment = halign
        ws.row_dimensions[1].height = 20
        for col in ws.columns:
            mx = max((len(str(c.value or '')) for c in col), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(mx + 2, 60)
        wb.save(str(tmp_out))

        stem = Path(f.filename).stem
        return send_file(str(tmp_out), as_attachment=True,
                         download_name=f'{stem}_normalise.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        for p in (tmp_in,):
            try:
                if p.exists(): p.unlink()
            except Exception:
                pass
        # tmp_out cleaned up after Flask sends it (on next request or GC)


@app.route('/admin/delete_generated', methods=['POST'])
def admin_delete_generated():
    data = request.get_json(force=True)
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    name = data.get('name') if isinstance(data, dict) else None
    if not name:
        return jsonify(error='name required'), 400
    safe = secure_filename(name)
    path = GENERATED_DIR / safe
    if not path.exists():
        return jsonify(error='File not found'), 404
    try:
        path.unlink()
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/admin/sessions')
def admin_list_sessions():
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    sessions = []
    for f in sorted(SESSIONS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix=='.json':
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                data = {}
            sessions.append({
                'id': f.stem,
                'script_name': data.get('script_name'),
                'group_name': data.get('group_name'),
                'rows': len(data.get('rows', [])),
                'mtime': f.stat().st_mtime
            })
    return jsonify(sessions=sessions)


@app.route('/admin/jobs')
def admin_list_jobs():
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    out = []
    for jid, info in list(jobs.items()):
        out.append({
            'id': jid,
            'status': info.get('status'),
            'progress': info.get('progress', 0),
            'phase': info.get('phase'),
            'video': info.get('video'),
            'output_name': info.get('output_name'),
        })
    return jsonify(jobs=out)


# Cache of expensive per-session metrics (syllable counting), keyed by session_id.
# Value: (file_mtime, metrics_dict). Recomputed only when the session file changes,
# so frequent monitoring polls stay cheap.
_session_metrics_cache = {}


def _session_metrics(session_id: str, path: Path, mtime: float):
    cached = _session_metrics_cache.get(session_id)
    if cached and cached[0] == mtime:
        return cached[1]

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    rows = data.get('rows') or []
    if not isinstance(rows, list):
        rows = []
    group_name = (data.get('group_name') or '').strip() or 'Sans nom'
    script_name = data.get('script_name') or ''
    extrait = Path(script_name).stem if script_name else ''

    total = len(rows)
    translated = 0
    quality_scores = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        detour = (r.get('detour') or '').strip()
        if not detour:
            continue
        translated += 1
        orig = r.get('orig_phonemes') or 0
        if orig:
            try:
                det_ph = count_syllables(detour, lang='fr')
            except Exception:
                det_ph = 0
            ratio = (det_ph / orig) * 100
            quality_scores.append(max(0.0, 100.0 - abs(ratio - 100.0)))

    metrics = {
        'group_name': group_name,
        'extrait': extrait,
        'rows_total': total,
        'rows_translated': translated,
        'progress_pct': round((translated / total) * 100) if total else 0,
        'quality_pct': round(sum(quality_scores) / len(quality_scores)) if quality_scores else None,
    }
    _session_metrics_cache[session_id] = (mtime, metrics)
    return metrics


# Real-time progress pushed by the editor pages as gauges update client-side,
# so monitoring reflects live typing instead of waiting for the 15s autosave.
# session_id -> {rows_total, rows_translated, progress_pct, quality_pct, ts}
LIVE_PROGRESS_TTL = 90
live_progress = {}


@app.route('/live/<session_id>', methods=['POST'])
def push_live_progress(session_id):
    if not _check_access_token(request):
        return jsonify(error='forbidden'), 403
    session_id = secure_filename(session_id)
    if not (SESSIONS_DIR / f'{session_id}.json').exists():
        return jsonify(error='Session introuvable'), 404
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}

    def _int(key):
        try:
            return max(0, int(data.get(key, 0)))
        except Exception:
            return 0

    quality = data.get('quality_pct')
    try:
        quality = None if quality is None else max(0, min(100, round(float(quality))))
    except Exception:
        quality = None

    live_progress[session_id] = {
        'rows_total': _int('rows_total'),
        'rows_translated': _int('rows_translated'),
        'progress_pct': max(0, min(100, _int('progress_pct'))),
        'quality_pct': quality,
        'ts': time.time(),
    }
    return jsonify(ok=True)


@app.route('/admin/monitoring')
def admin_monitoring():
    """Aggregate per-group progress for the monitoring dashboard: overall
    dubbing-adaptation progress, average phrase-match quality, and rythmo
    generation job status/downloads."""
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403

    groups = []
    seen_ids = set()
    for f in sorted(SESSIONS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not (f.is_file() and f.suffix == '.json'):
            continue
        session_id = f.stem
        seen_ids.add(session_id)
        mtime = f.stat().st_mtime
        metrics = _session_metrics(session_id, f, mtime)
        if metrics is None:
            continue
        group_name = metrics['group_name']

        live = live_progress.get(session_id)
        if live and (time.time() - live.get('ts', 0)) < LIVE_PROGRESS_TTL:
            rows_total = live['rows_total']
            rows_translated = live['rows_translated']
            progress_pct = live['progress_pct']
            quality_pct = live['quality_pct']
        else:
            rows_total = metrics['rows_total']
            rows_translated = metrics['rows_translated']
            progress_pct = metrics['progress_pct']
            quality_pct = metrics['quality_pct']

        safe_group = sanitize_group_name(group_name)
        expected_output = f'{safe_group}_Sync.mp4'
        video_path = GENERATED_DIR / expected_output
        detx_path = GENERATED_DIR / f'{safe_group}_Sync.detx'

        job_info = None
        for jid, info in jobs.items():
            if info.get('output_name') != expected_output:
                continue
            if job_info is None or info.get('created_at', 0) >= job_info.get('created_at', 0):
                job_info = {
                    'id': jid,
                    'status': info.get('status'),
                    'progress': info.get('progress', 0),
                    'phase': info.get('phase'),
                    'error': info.get('error'),
                    'created_at': info.get('created_at'),
                }

        video_exists = video_path.exists()
        detx_exists = detx_path.exists()
        groups.append({
            'session_id': session_id,
            'group_name': group_name,
            'extrait': metrics['extrait'],
            'mtime': mtime,
            'rows_total': rows_total,
            'rows_translated': rows_translated,
            'progress_pct': progress_pct,
            'quality_pct': quality_pct,
            'job': job_info,
            'video_ready': video_exists,
            'video_name': video_path.name if video_exists else None,
            'video_mtime': video_path.stat().st_mtime if video_exists else None,
            'detx_ready': detx_exists,
            'detx_name': detx_path.name if detx_exists else None,
            'detx_mtime': detx_path.stat().st_mtime if detx_exists else None,
        })

    # drop cache entries for sessions that no longer exist
    for stale_id in (set(_session_metrics_cache) - seen_ids):
        _session_metrics_cache.pop(stale_id, None)
    for stale_id in (set(live_progress) - seen_ids):
        live_progress.pop(stale_id, None)

    return jsonify(groups=groups, generated_at=time.time())


@app.route('/monitoring.html')
def monitoring_page():
    return send_from_directory('.', 'monitoring.html')


@app.route('/admin/cleanup_jobs', methods=['POST'])
def admin_cleanup_jobs():
    # accept token either as query param or in JSON body
    try:
        body = request.get_json(force=False)
    except Exception:
        body = None
    if not _check_admin_token(request, body):
        return jsonify(error='forbidden'), 403
    removed = []
    for jid in list(jobs.keys()):
        info = jobs.get(jid)
        if not info:
            continue
        # remove jobs not currently running or queued
        if info.get('status') not in ('running', 'queued'):
            jobs.pop(jid, None)
            removed.append(jid)
    return jsonify(ok=True, removed=removed)


@app.route('/admin/stop_job', methods=['POST'])
def admin_stop_job():
    data = request.get_json(force=True)
    jid = data.get('job_id') if isinstance(data, dict) else None
    if not jid:
        return jsonify(error='job_id required'), 400
    info = jobs.get(jid)
    if not info:
        return jsonify(error='Job not found'), 404
    # mark abort requested so run_job can react if the subprocess isn't started yet
    info['abort_requested'] = True
    proc = info.get('proc')
    pid = info.get('pid')
    # try to kill via proc handle if available
    if proc:
        try:
            proc.kill()
        except Exception as e:
            # fallthrough to try PID kill
            try:
                if pid:
                    os.kill(pid, signal.SIGTERM)
            except Exception:
                return jsonify(error=str(e)), 500
    else:
        # no proc handle yet; if we have PID, try to kill by PID
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                # process may not exist yet; we'll rely on abort_requested flag
                pass
    info['status'] = 'error'
    info['error'] = 'Aborted by user'
    return jsonify(ok=True)


@app.route('/admin/session/<session_id>')
def serve_session(session_id):
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    path = SESSIONS_DIR / f'{secure_filename(session_id)}.json'
    if not path.exists():
        return jsonify(error='Session not found'), 404
    return send_file(str(path), as_attachment=True, download_name=path.name)


@app.route('/session/create', methods=['POST'])
def create_session_from_rows():
    """Create a server-side session file from posted rows and optional metadata.
    Accepts JSON: { rows: [...], script_name?: str, group_name?: str }
    Returns: { session_id: <id> }
    """
    data = request.get_json(force=True)
    if not data or 'rows' not in data or not isinstance(data.get('rows'), list):
        return jsonify(error='rows required'), 400
    session_id = str(uuid.uuid4())[:12]
    # ensure each row has orig_phonemes computed so clients see initial values
    rows = data.get('rows', [])
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get('orig_phonemes') is None:
            try:
                r['orig_phonemes'] = count_syllables(r.get('text', ''), lang=data.get('lang', 'fr'))
            except Exception:
                r['orig_phonemes'] = 0
    session_data = {'rows': rows}
    if isinstance(data.get('script_name'), str):
        session_data['script_name'] = data.get('script_name')
    if isinstance(data.get('group_name'), str) and data.get('group_name').strip():
        session_data['group_name'] = data.get('group_name').strip()
    try:
        (SESSIONS_DIR / f'{session_id}.json').write_text(json.dumps(session_data, ensure_ascii=False), encoding='utf-8')
        return jsonify(session_id=session_id)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/session/stream/<session_id>')
def session_stream(session_id):
    """SSE endpoint that streams session file changes in near-real-time.

    The client can open an EventSource to receive the full session JSON
    whenever the underlying session file is updated. This replaces
    client-side polling (setInterval) for `GET /session/<id>`.
    """
    path = SESSIONS_DIR / f'{secure_filename(session_id)}.json'
    if not path.exists():
        return jsonify(error='Session not found'), 404

    def stream():
        try:
            last_mtime = path.stat().st_mtime
        except Exception:
            last_mtime = None
        # send initial payload
        try:
            payload = path.read_text(encoding='utf-8')
        except Exception:
            payload = '{}'
        yield f'data: {payload}\n\n'

        while True:
            try:
                if not path.exists():
                    yield 'data: {"error":"Session not found"}\n\n'
                    break
                mtime = path.stat().st_mtime
                if last_mtime is None or mtime > last_mtime:
                    try:
                        payload = path.read_text(encoding='utf-8')
                    except Exception:
                        payload = '{}'
                    yield f'data: {payload}\n\n'
                    last_mtime = mtime
                # small sleep to avoid tight loop but keep near-realtime
                time.sleep(0.5)
            except GeneratorExit:
                break
            except Exception:
                time.sleep(1)

    return Response(stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/session/<session_id>')
def get_session_json(session_id):
    """Return the session JSON (used by the client fallback fetch)."""
    if not _check_access_token(request) and not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    path = SESSIONS_DIR / f'{secure_filename(session_id)}.json'
    if not path.exists():
        return jsonify(error='Session not found'), 404
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/phonemize', methods=['POST'])
def phonemize():
    """Compatibility endpoint: return a numeric syllable count under the
    `phonemes` key so the existing UI doesn't need schema changes.
    Expects JSON { text: <str>, lang: <str> }.
    """
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        data = {}
    text = data.get('text') if isinstance(data, dict) else None
    lang = data.get('lang') if isinstance(data, dict) else 'fr'
    if not isinstance(text, str):
        return jsonify(error='text required'), 400
    try:
        n = count_syllables(text, lang=lang)
        return jsonify(phonemes=n)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/admin/delete_session', methods=['POST'])
def admin_delete_session():
    data = request.get_json(force=True)
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    sid = data.get('id') if isinstance(data, dict) else None
    if not sid:
        return jsonify(error='id required'), 400
    path = SESSIONS_DIR / f'{secure_filename(sid)}.json'
    if not path.exists():
        return jsonify(error='Session not found'), 404
    try:
        path.unlink()
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(error=str(e)),500


# ---------------------------------------------------------------------------
# Setup tab: content directories, service control, access codes.
# All of these (and /dashboard.html) are restricted to the local machine —
# the native admin app is the only intended client, never the LAN.
# ---------------------------------------------------------------------------
LAUNCH_AGENT_LABEL = 'com.lesateliersdoublage.server'
LOCAL_SECRET_FILE = Path('local_admin.secret')


def _is_loopback(req):
    return (req.remote_addr or '') in ('127.0.0.1', '::1')


def _get_local_secret():
    """Long-lived secret used by the native admin app to auto-authenticate
    without a human ever typing a password. Only readable on the local
    filesystem (chmod 600), and /admin/local_auth only accepts loopback
    requests, so it cannot be exercised remotely."""
    if not LOCAL_SECRET_FILE.exists():
        value = secrets.token_hex(32)
        LOCAL_SECRET_FILE.write_text(value, encoding='utf-8')
        os.chmod(LOCAL_SECRET_FILE, 0o600)
        return value
    return LOCAL_SECRET_FILE.read_text(encoding='utf-8').strip()


_LOCAL_SECRET = _get_local_secret()


@app.route('/admin/local_auth', methods=['POST'])
def admin_local_auth():
    """Exchange the local secret file for a long-lived admin token. Used only
    by the native admin app running on this machine."""
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    data = request.get_json(silent=True) or {}
    secret = str(data.get('secret', ''))
    if not secret or not hmac.compare_digest(secret, _LOCAL_SECRET):
        return jsonify(error='forbidden'), 403
    token = str(uuid.uuid4())
    admin_tokens[token] = {'expiry': time.time() + 12 * 3600}
    return jsonify(token=token)


def _get_local_ip():
    """Best-effort local network IP (not 127.0.0.1); falls back to loopback."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def _service_pid():
    """Current running server PID. Checks run_server.pid first (manual /
    install.command start), then falls back to querying launchctl (LaunchAgent
    start, which does not maintain a pidfile)."""
    pid_file = Path('run_server.pid')
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding='utf-8').strip())
            os.kill(pid, 0)  # raises if not alive
            return pid
        except Exception:
            pass
    try:
        uid = os.getuid()
        out = subprocess.run(['launchctl', 'print', f'gui/{uid}/{LAUNCH_AGENT_LABEL}'],
                              capture_output=True, timeout=5, text=True)
        if out.returncode == 0:
            m = re.search(r'^\s*pid\s*=\s*(\d+)', out.stdout, re.MULTILINE)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return None


@app.route('/admin/setup_info')
def admin_setup_info():
    """Admin endpoint: current content-directory config, service status, and
    network address, for the Setup tab."""
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    cfg = _load_paths_config()
    pid = _service_pid()
    return jsonify(ok=True, paths={
        'videos_dir': str(VIDEOS_DIR.resolve()),
        'scripts_dir': str(SCRIPTS_DIR.resolve()),
        'vi_dir': str(VI_DIR.resolve()),
        'repartition_csv': str(REPARTITION_CSV.resolve()),
    }, port=cfg.get('port', '1348'), ip=_get_local_ip(), service={
        'running': pid is not None,
        'pid': pid,
    })


@app.route('/admin/setup_paths', methods=['POST'])
def admin_setup_paths():
    """Admin endpoint: update content-directory paths (videos/scripts/VI/csv) and
    port. Changes are written to config.json; a restart is required to apply
    them to the running process (paths are read once at startup)."""
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    data = request.get_json(silent=True) or {}
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    updates = {}
    for key in ('videos_dir', 'scripts_dir', 'vi_dir', 'repartition_csv', 'port'):
        val = data.get(key)
        if val:
            updates[key] = str(val).strip()
    if not updates:
        return jsonify(error='no valid fields'), 400
    # create missing directories eagerly so the Setup tab can offer "create new"
    for key in ('videos_dir', 'scripts_dir', 'vi_dir'):
        if key in updates:
            try:
                Path(updates[key]).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return jsonify(error=f'impossible de créer {updates[key]}: {e}'), 400
    if 'repartition_csv' in updates:
        p = Path(updates['repartition_csv'])
        if not p.exists():
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(
                    'Fichier vidéo,Nombre de personnages,F,H,catégorie,SPEED,Afficher\n',
                    encoding='utf-8-sig')
            except Exception as e:
                return jsonify(error=f'impossible de créer {updates["repartition_csv"]}: {e}'), 400
    cfg = save_paths_config(updates)
    return jsonify(ok=True, paths=cfg, restart_required=True)


@app.route('/admin/browse_dir')
def admin_browse_dir():
    """Admin endpoint: list subdirectories of a given filesystem path, for a
    simple server-side folder browser (browsers can't expose absolute host
    paths via <input type=file>)."""
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    raw = request.args.get('path') or str(Path.home())
    try:
        target = Path(raw).expanduser().resolve()
        if not target.exists() or not target.is_dir():
            return jsonify(error='dossier introuvable'), 404
        dirs = sorted(
            [f.name for f in target.iterdir() if f.is_dir() and not f.name.startswith('.')],
            key=lambda s: s.lower())
        return jsonify(ok=True, path=str(target), parent=str(target.parent), dirs=dirs)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route('/admin/change_admin_code', methods=['POST'])
def admin_change_admin_code():
    """Admin endpoint: set a new 4-digit admin code (rewrites admin_code.hash)."""
    global _ADMIN_CODE_HASH
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    data = request.get_json(silent=True) or {}
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    code = str(data.get('code', '')).strip()
    if not re.match(r'^\d{4}$', code):
        return jsonify(error='le code admin doit comporter 4 chiffres'), 400
    digest = hashlib.sha256(code.encode('utf-8')).hexdigest()
    try:
        Path('admin_code.hash').write_text(digest, encoding='utf-8')
        os.chmod('admin_code.hash', 0o600)
    except Exception as e:
        return jsonify(error=str(e)), 500
    _ADMIN_CODE_HASH = digest
    return jsonify(ok=True)


@app.route('/admin/change_master_code', methods=['POST'])
def admin_change_master_code():
    """Admin endpoint: set a new master access code (rewrites master_code.hash)."""
    global MASTER_CODE_HASH
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    data = request.get_json(silent=True) or {}
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    code = str(data.get('code', '')).strip()
    if not code:
        return jsonify(error='code vide'), 400
    digest = hashlib.sha256(code.encode('utf-8')).hexdigest()
    try:
        Path('master_code.hash').write_text(digest, encoding='utf-8')
        os.chmod('master_code.hash', 0o600)
    except Exception as e:
        return jsonify(error=str(e)), 500
    MASTER_CODE_HASH = digest
    return jsonify(ok=True)


@app.route('/admin/service_status')
def admin_service_status():
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    if not _check_admin_token(request):
        return jsonify(error='forbidden'), 403
    pid = _service_pid()
    uid = os.getuid()
    launch_agent_loaded = False
    try:
        out = subprocess.run(['launchctl', 'print', f'gui/{uid}/{LAUNCH_AGENT_LABEL}'],
                              capture_output=True, timeout=5)
        launch_agent_loaded = out.returncode == 0
    except Exception:
        pass
    return jsonify(ok=True, running=pid is not None, pid=pid,
                   launch_agent_loaded=launch_agent_loaded)


def _log_service_control(action, result):
    """Record launchctl output because the service may disappear immediately."""
    log_path = Path('launchagent.log')
    output = (result.stdout or '').strip()
    error = (result.stderr or '').strip()
    try:
        with log_path.open('a', encoding='utf-8') as log:
            log.write(f'[service_{action}] returncode={result.returncode}\n')
            if output:
                log.write(f'[service_{action}] stdout: {output}\n')
            if error:
                log.write(f'[service_{action}] stderr: {error}\n')
    except Exception:
        pass


def _log_service_control_error(action, error):
    try:
        with Path('launchagent.log').open('a', encoding='utf-8') as log:
            log.write(f'[service_{action}] exception: {error}\n')
    except Exception:
        pass


@app.route('/admin/service_restart', methods=['POST'])
def admin_service_restart():
    """Admin endpoint: restart the service via launchctl kickstart. Runs after a
    short delay in a background thread so this request can return first."""
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    data = request.get_json(silent=True) or {}
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    uid = os.getuid()
    plist_path = Path.home() / 'Library' / 'LaunchAgents' / f'{LAUNCH_AGENT_LABEL}.plist'

    def _do_restart():
        time.sleep(1)
        try:
            loaded = subprocess.run(
                ['launchctl', 'print', f'gui/{uid}/{LAUNCH_AGENT_LABEL}'],
                capture_output=True, check=False, timeout=5)
            if loaded.returncode != 0:
                bootstrap = subprocess.run(
                    ['launchctl', 'bootstrap', f'gui/{uid}', str(plist_path)],
                    capture_output=True, text=True, check=False, timeout=10)
                _log_service_control('bootstrap', bootstrap)
                if bootstrap.returncode != 0:
                    return
            result = subprocess.run(
                ['launchctl', 'kickstart', '-k', f'gui/{uid}/{LAUNCH_AGENT_LABEL}'],
                capture_output=True, text=True, check=False, timeout=10)
            _log_service_control('restart', result)
        except Exception as exc:
            _log_service_control_error('restart', exc)

    threading.Thread(target=_do_restart, daemon=True).start()
    return jsonify(ok=True, message='Redémarrage en cours…')


@app.route('/admin/service_stop', methods=['POST'])
def admin_service_stop():
    """Admin endpoint: stop the service (unloads the LaunchAgent so it does not
    auto-restart). Requires the LaunchAgent + a manual relaunch (double-click
    'Démarrer le serveur.command') to bring it back up."""
    if not _is_loopback(request):
        return jsonify(error='forbidden'), 403
    data = request.get_json(silent=True) or {}
    if not _check_admin_token(request, data):
        return jsonify(error='forbidden'), 403
    uid = os.getuid()

    def _do_stop():
        time.sleep(1)
        try:
            result = subprocess.run(
                ['launchctl', 'bootout', f'gui/{uid}/{LAUNCH_AGENT_LABEL}'],
                capture_output=True, text=True, check=False, timeout=10)
            _log_service_control('stop', result)
        except Exception as exc:
            _log_service_control_error('stop', exc)

    threading.Thread(target=_do_stop, daemon=True).start()
    return jsonify(ok=True, message='Arrêt en cours…')


@app.errorhandler(413)
def too_large(e):
    return jsonify(error=f'Fichier trop volumineux (max {MAX_UPLOAD_MB} MB)'), 413


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--ssl-cert', default=None,
                        help='Path to TLS certificate (PEM) to enable HTTPS')
    parser.add_argument('--ssl-key', default=None,
                        help='Path to TLS private key (PEM) to enable HTTPS')
    args = parser.parse_args()

    app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024
    if args.ssl_cert and args.ssl_key:
        cert_path = Path(args.ssl_cert)
        key_path = Path(args.ssl_key)
        if cert_path.exists() and key_path.exists():
            print(f'Rythmo Sync Server - https://localhost:{args.port} (TLS enabled)')
            ssl_ctx = (str(cert_path.resolve()), str(key_path.resolve()))
            app.run(host=args.host, port=args.port, debug=False, threaded=True, ssl_context=ssl_ctx)
        else:
            print('TLS certificate or key not found; starting without TLS')
            print(f'Rythmo Sync Server - http://localhost:{args.port}')
            app.run(host=args.host, port=args.port, debug=False, threaded=True)
    else:
        print(f'Rythmo Sync Server - http://localhost:{args.port}')
        app.run(host=args.host, port=args.port, debug=False, threaded=True)
