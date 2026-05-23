# -*- coding: utf-8 -*-
"""
image_cli.py — File-based image management for gantt-viewer.

Images live in pilots/{slug}/media/{num}-{idx}.{ext} where:
  - num  = item number (1-based, as in data.json)
  - idx  = slot index (0-based; carousel/story can have multiple)
  - ext  = jpg | jpeg | png | webp | gif

Commands:
  add     <slug> <num> <file>           → next free slot for item
  replace <slug> <num> <idx> <file>     → overwrite specific slot
  remove  <slug> <num> <idx>            → delete specific slot
  list    <slug>                        → show all media files
  sync    <slug> <folder>               → bulk import (filenames like '5-0.jpg' or just '5.jpg')

After any mutation, you should rebuild the gantt:
    python build.py --data pilots/<slug>/data.json --logo assets/logo.png \\
                    --out docs/<slug>/index.html --mode zeliger
"""
from __future__ import annotations

import argparse
import shutil
import sys
import io
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).parent
PILOTS = ROOT / 'pilots'
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def media_dir(slug: str) -> Path:
    d = PILOTS / slug / 'media'
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_media(slug: str) -> dict[int, list[tuple[int, Path]]]:
    """Return {num: [(idx, path), ...]} for an existing pilot."""
    out: dict[int, list[tuple[int, Path]]] = {}
    d = media_dir(slug)
    for f in sorted(d.iterdir()):
        if not f.is_file() or f.suffix.lower() not in ALLOWED_EXT:
            continue
        stem = f.stem
        if '-' not in stem:
            continue
        try:
            num_str, idx_str = stem.split('-', 1)
            num = int(num_str)
            idx = int(idx_str)
        except ValueError:
            continue
        out.setdefault(num, []).append((idx, f))
    for num in out:
        out[num].sort(key=lambda t: t[0])
    return out


def next_free_slot(slug: str, num: int) -> int:
    by_num = list_media(slug)
    if num not in by_num:
        return 0
    used = {idx for (idx, _) in by_num[num]}
    i = 0
    while i in used:
        i += 1
    return i


def cmd_add(slug: str, num: int, src: Path) -> None:
    if not src.exists():
        raise SystemExit(f'ERROR: source file not found: {src}')
    if src.suffix.lower() not in ALLOWED_EXT:
        raise SystemExit(f'ERROR: unsupported extension {src.suffix} (allowed: {", ".join(sorted(ALLOWED_EXT))})')
    idx = next_free_slot(slug, num)
    if idx >= 10:
        raise SystemExit('ERROR: item already has 10 images (max)')
    dst = media_dir(slug) / f'{num}-{idx}{src.suffix.lower()}'
    shutil.copy2(src, dst)
    print(f'ADDED  item #{num} slot {idx} → {dst.relative_to(ROOT)}')


def cmd_replace(slug: str, num: int, idx: int, src: Path) -> None:
    if not src.exists():
        raise SystemExit(f'ERROR: source file not found: {src}')
    if src.suffix.lower() not in ALLOWED_EXT:
        raise SystemExit(f'ERROR: unsupported extension {src.suffix}')
    # Remove ALL existing files for this num+idx (any extension)
    d = media_dir(slug)
    removed = False
    for f in d.iterdir():
        if f.stem == f'{num}-{idx}' and f.suffix.lower() in ALLOWED_EXT:
            f.unlink()
            removed = True
    dst = d / f'{num}-{idx}{src.suffix.lower()}'
    shutil.copy2(src, dst)
    print(f'{"REPLACED" if removed else "ADDED  "} item #{num} slot {idx} → {dst.relative_to(ROOT)}')


def cmd_remove(slug: str, num: int, idx: int) -> None:
    d = media_dir(slug)
    found = False
    for f in d.iterdir():
        if f.stem == f'{num}-{idx}' and f.suffix.lower() in ALLOWED_EXT:
            f.unlink()
            print(f'REMOVED {f.relative_to(ROOT)}')
            found = True
    if not found:
        print(f'(no file for item #{num} slot {idx})')


def cmd_list(slug: str) -> None:
    by_num = list_media(slug)
    if not by_num:
        print(f'(no media files in {media_dir(slug)})')
        return
    print(f'{slug}:')
    for num in sorted(by_num.keys()):
        slots = ', '.join(str(idx) for (idx, _) in by_num[num])
        print(f'  item #{num:>3}: {len(by_num[num])} image(s) — slots: [{slots}]')


def cmd_sync(slug: str, folder: Path) -> None:
    """Bulk import all files from `folder` whose names match {num}-{idx}.ext or {num}.ext."""
    if not folder.exists():
        raise SystemExit(f'ERROR: folder not found: {folder}')
    d = media_dir(slug)
    imported = 0
    for f in sorted(folder.iterdir()):
        if not f.is_file() or f.suffix.lower() not in ALLOWED_EXT:
            continue
        stem = f.stem
        # Accept {num}.ext or {num}-{idx}.ext
        try:
            if '-' in stem:
                num_str, idx_str = stem.split('-', 1)
                num = int(num_str)
                idx = int(idx_str)
            else:
                num = int(stem)
                idx = next_free_slot(slug, num)
        except ValueError:
            print(f'  SKIP {f.name} (filename must be NUM.ext or NUM-IDX.ext)')
            continue
        dst = d / f'{num}-{idx}{f.suffix.lower()}'
        shutil.copy2(f, dst)
        print(f'  IMPORTED {f.name} → {dst.name}')
        imported += 1
    print(f'\nDone. {imported} file(s) imported to {d.relative_to(ROOT)}')


def main():
    p = argparse.ArgumentParser(description='Manage gantt media files (file-based, committed to repo).')
    sub = p.add_subparsers(dest='cmd', required=True)

    a = sub.add_parser('add', help='Add a new image to the next free slot of an item')
    a.add_argument('slug'); a.add_argument('num', type=int); a.add_argument('file', type=Path)

    r = sub.add_parser('replace', help='Replace a specific slot')
    r.add_argument('slug'); r.add_argument('num', type=int); r.add_argument('idx', type=int); r.add_argument('file', type=Path)

    rm = sub.add_parser('remove', help='Delete a specific slot')
    rm.add_argument('slug'); rm.add_argument('num', type=int); rm.add_argument('idx', type=int)

    ls = sub.add_parser('list', help='Show all media files for a pilot')
    ls.add_argument('slug')

    sy = sub.add_parser('sync', help='Bulk import from a folder')
    sy.add_argument('slug'); sy.add_argument('folder', type=Path)

    args = p.parse_args()
    if args.cmd == 'add':     cmd_add(args.slug, args.num, args.file)
    elif args.cmd == 'replace': cmd_replace(args.slug, args.num, args.idx, args.file)
    elif args.cmd == 'remove':  cmd_remove(args.slug, args.num, args.idx)
    elif args.cmd == 'list':    cmd_list(args.slug)
    elif args.cmd == 'sync':    cmd_sync(args.slug, args.folder)


if __name__ == '__main__':
    main()
