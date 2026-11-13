#!/usr/bin/env python3
"""Count syllables using pyphen (French-focused).

Usage:
  - Count words in a single string:
      python scripts/syllable_count.py "bonjour tout le monde"
  - Count lines in a script file and report totals:
      python scripts/syllable_count.py -f path/to/script.txt

This is a lightweight replacement for phonemization when you only need
syllable counts (faster, local, no external binaries).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable

import pyphen


dic = pyphen.Pyphen(lang='fr_FR')


def count_word(word: str) -> int:
    if not word:
        return 0
    w = word.strip()
    w = w.strip("\"'«».,;:!?()[]")
    if not w:
        return 0
    parts = dic.inserted(w)
    if not parts:
        return 1
    return max(1, len(parts.split('-')))


def count_text(text: str) -> int:
    words = [w for w in text.split() if w.strip()]
    return sum(count_word(w) for w in words)


def count_lines(lines: Iterable[str]) -> tuple[int, int]:
    """Return (lines_counted, total_syllables)"""
    total = 0
    n = 0
    for L in lines:
        n += 1
        total += count_text(L)
    return n, total


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Count syllables using pyphen (fr_FR)')
    p.add_argument('-f', '--file', type=Path, help='Text file (one phrase per line)')
    p.add_argument('text', nargs='*', help='Text to count (if no -f)')
    args = p.parse_args(argv)

    if args.file:
        if not args.file.exists():
            print(f'File not found: {args.file}', file=sys.stderr)
            return 2
        with args.file.open('r', encoding='utf-8', errors='replace') as f:
            lines = [l.strip() for l in f if l.strip()]
        n, total = count_lines(lines)
        print(f'Lines: {n} — Total syllables: {total}')
        return 0

    if args.text:
        text = ' '.join(args.text).strip()
        total = count_text(text)
        print(total)
        return 0

    # interactive / stdin
    if not sys.stdin.isatty():
        data = sys.stdin.read().strip()
        if data:
            n, total = count_lines(data.splitlines())
            print(f'Lines: {n} — Total syllables: {total}')
            return 0

    p.print_help()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
