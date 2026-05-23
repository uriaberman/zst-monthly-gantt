# -*- coding: utf-8 -*-
"""
build_all.py — Rebuild every gantt in pilots/registry.json.

Use this when:
  - data.json changed for ANY pilot (run from GitHub Action)
  - build.py logic changed (regenerate all HTMLs)
  - bulk publish after multiple manual edits

Usage:
    python build_all.py
    python build_all.py --only shlichut-horaa adavot   (subset)
    python build_all.py --changed pilots/shlichut-horaa/data.json   (rebuild only targets affected by this file)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).parent


def load_registry() -> dict:
    return json.loads((ROOT / 'pilots' / 'registry.json').read_text(encoding='utf-8'))


def build_one(slug: str, target: dict) -> bool:
    cmd = [
        sys.executable, str(ROOT / 'build.py'),
        '--data', target['data'],
        '--logo', 'assets/logo.png',
        '--out',  target['out'],
        '--mode', target['mode'],
    ]
    print(f'\n→ Building {slug} ({target["mode"]})')
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        print(f'  FAILED ({r.returncode}):')
        print(r.stdout)
        print(r.stderr)
        return False
    # Tail the last 4 lines
    for line in r.stdout.strip().split('\n')[-4:]:
        print(f'  {line}')
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', nargs='*', help='Only rebuild these slugs')
    ap.add_argument('--changed', nargs='*', help='Paths of changed files; rebuild only targets whose data.json matches')
    args = ap.parse_args()

    reg = load_registry()
    targets = reg['targets']

    if args.only:
        slugs = [s for s in args.only if s in targets]
    elif args.changed:
        slugs = []
        for slug, t in targets.items():
            for ch in args.changed:
                ch_norm = ch.replace('\\', '/')
                if t['data'].replace('\\', '/') == ch_norm:
                    slugs.append(slug)
        slugs = list(dict.fromkeys(slugs))  # dedupe
    else:
        slugs = list(targets.keys())

    if not slugs:
        print('Nothing to rebuild.')
        return 0

    print(f'Rebuilding {len(slugs)} target(s): {", ".join(slugs)}')
    ok = 0
    for slug in slugs:
        if build_one(slug, targets[slug]):
            ok += 1
    print(f'\nDone. {ok}/{len(slugs)} succeeded.')
    return 0 if ok == len(slugs) else 1


if __name__ == '__main__':
    sys.exit(main())
