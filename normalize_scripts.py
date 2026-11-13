#!/usr/bin/env python3
"""
Normalisation des scripts AD → SCRIPTS NORMALISES / SCRIPTS A REVOIR

Pour chaque script dans AD/SCRIPTS/ (.xlsx, .xls, .ods) :
  - Réutilise read_script() + detect_columns() de generate_sync.py
  - Supprime les colonnes entièrement vides (hors ligne d'en-tête)
  - Reconstruit un fichier XLSX avec 4 colonnes : TC IN / TC OUT / CHARACTER / TEXTE
  - Si la détection échoue → copie dans SCRIPTS A REVOIR avec note d'erreur

Usage:
    python normalize_scripts.py
"""

import importlib.util, sys
from pathlib import Path
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

# ── Charger generate_sync pour réutiliser ses fonctions ──────────
ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('generate_sync', ROOT / 'generate_sync.py')
mod  = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

read_script     = mod.read_script
detect_columns  = mod.detect_columns

# ── Dossiers ─────────────────────────────────────────────────────
SCRIPTS_DIR  = ROOT / 'SCRIPTS'
OUT_OK       = ROOT / 'SCRIPTS NORMALISES'
OUT_KO       = ROOT / 'SCRIPTS A REVOIR'

OUT_OK.mkdir(exist_ok=True)
OUT_KO.mkdir(exist_ok=True)

HEADER = ['TC IN', 'TC OUT', 'CHARACTER', 'TEXTE']

# Style en-tête
HEADER_FILL  = PatternFill('solid', fgColor='1F4E79')
HEADER_FONT  = Font(bold=True, color='FFFFFF', name='Calibri', size=11)
HEADER_ALIGN = Alignment(horizontal='center', vertical='center')

def style_header(ws):
    for cell in ws[1]:
        cell.fill  = HEADER_FILL
        cell.font  = HEADER_FONT
        cell.alignment = HEADER_ALIGN
    ws.row_dimensions[1].height = 20

def auto_col_width(ws):
    for col in ws.columns:
        max_len = max((len(str(c.value or '')) for c in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)

def write_ok(stem: str, rows: list[list]):
    path = OUT_OK / f'{stem}.xlsx'
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Script'
    ws.append(HEADER)
    for row in rows:
        ws.append(row)
    style_header(ws)
    auto_col_width(ws)
    wb.save(path)
    return path

def write_ko(src: Path, reason: str):
    """Copie le fichier original dans SCRIPTS A REVOIR et ajoute une note."""
    import shutil
    dest = OUT_KO / (src.stem + src.suffix)
    shutil.copy2(src, dest)
    # Fichier texte d'explication
    (OUT_KO / f'{src.stem}.txt').write_text(
        f'Fichier : {src.name}\nErreur  : {reason}\n', encoding='utf-8')

# ── Traitement ───────────────────────────────────────────────────
files = sorted(
    f for f in SCRIPTS_DIR.iterdir()
    if f.suffix.lower() in ('.xlsx', '.xls', '.ods')
)

ok_count = ko_count = 0

for f in files:
    try:
        df = read_script(f)

        # Supprimer colonnes entièrement vides (hors header, déjà géré par read_script)
        df = df.dropna(axis=1, how='all')
        df = df.loc[:, df.astype(str).apply(
            lambda col: col.str.strip().ne('').any()
        )]

        char_col, start_col, end_col, text_col = detect_columns(df)

        rows = []
        for _, row in df.iterrows():
            tc_in  = str(row[start_col]).strip() if pd.notna(row[start_col]) else ''
            tc_out = str(row[end_col]).strip()   if pd.notna(row[end_col])   else ''
            char   = str(row[char_col]).strip()  if pd.notna(row[char_col])  else ''
            text   = str(row[text_col]).strip()  if pd.notna(row[text_col])  else ''
            # Ignorer lignes vides
            if not any([tc_in, tc_out, char, text]):
                continue
            rows.append([tc_in, tc_out, char, text])

        if not rows:
            raise ValueError('Aucune ligne de données après filtrage')

        dest = write_ok(f.stem, rows)
        print(f'[OK] {f.name:60s}  →  {dest.name}  ({len(rows)} lignes)')
        ok_count += 1

    except Exception as e:
        write_ko(f, str(e))
        print(f'[KO] {f.name:60s}  →  SCRIPTS A REVOIR  ({e})')
        ko_count += 1

print(f'\n{"="*60}')
print(f'Normalisés : {ok_count}   |   À revoir : {ko_count}   |   Total : {ok_count+ko_count}')
