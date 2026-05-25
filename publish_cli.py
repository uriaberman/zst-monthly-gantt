# -*- coding: utf-8 -*-
"""
publish_cli.py — Apply a publish payload from the browser to data.json, snapshot, and rebuild.

The browser's "פרסם שינויים" button downloads a JSON like:
  {
    "client_key": "shlichut_horaa",
    "generated_at": "...",
    "changes": {
      "items": {
        "5":  {"date": "2026-06-15", "status": "אושר"},
        "12": {"copy": "טקסט חדש"}
      },
      "deletions": ["7", "10"]   <-- Iron Rule #20: permanent removal from data.json
    }
  }

This script:
  1. Snapshots current data.json to pilots/{slug}/snapshots/{timestamp}.json
  2. Applies edits to data.json
  3. Removes items listed in `deletions` (NOT recoverable except via --rollback)
  4. (caller is expected to run build.py afterward)

Usage:
  python publish_cli.py --slug shlichut-horaa --payload path/to/publish-blob.json
  python publish_cli.py --slug shlichut-horaa --rollback           → revert to latest snapshot
  python publish_cli.py --slug shlichut-horaa --list-snapshots     → list snapshots
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import io
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).parent
PILOTS = ROOT / 'pilots'


def snapshots_dir(slug: str) -> Path:
    d = PILOTS / slug / 'snapshots'
    d.mkdir(parents=True, exist_ok=True)
    return d


def take_snapshot(slug: str, data_path: Path) -> Path:
    """Copy current data.json to snapshots/{YYYY-MM-DD_HH-MM-SS}.json."""
    ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    dst = snapshots_dir(slug) / f'{ts}.json'
    shutil.copy2(data_path, dst)
    return dst


def list_snapshots(slug: str) -> list[Path]:
    d = snapshots_dir(slug)
    return sorted([f for f in d.glob('*.json') if f.is_file()])


def apply_changes(slug: str, payload_path: Path) -> dict:
    """Merge payload changes into data.json. Returns summary dict."""
    data_path = PILOTS / slug / 'data.json'
    if not data_path.exists():
        raise SystemExit(f'ERROR: data file not found: {data_path}')
    payload = json.loads(payload_path.read_text(encoding='utf-8'))

    # Snapshot before modifying
    snap = take_snapshot(slug, data_path)
    print(f'SNAPSHOT  {snap.relative_to(ROOT)}')

    data = json.loads(data_path.read_text(encoding='utf-8'))
    items_by_num = {str(it['num']): it for it in data['items']}

    changes = payload.get('changes', {}).get('items', {})
    deletions = payload.get('changes', {}).get('deletions', []) or []
    summary = {'date_changes': 0, 'status_changes': 0, 'copy_changes': 0, 'deletions': 0, 'missing': []}

    for num_str, draft in changes.items():
        it = items_by_num.get(num_str)
        if not it:
            summary['missing'].append(num_str)
            continue
        if 'date' in draft:
            it['date_iso'] = draft['date']
            summary['date_changes'] += 1
            print(f'  item #{num_str}: date → {draft["date"]}')
        if 'status' in draft:
            it['status'] = draft['status']
            summary['status_changes'] += 1
            print(f'  item #{num_str}: status → {draft["status"]}')
        if 'copy' in draft:
            it['copy_final'] = draft['copy']
            summary['copy_changes'] += 1
            print(f'  item #{num_str}: copy updated ({len(draft["copy"])} chars)')

    # Iron Rule #20: permanent deletions. Filter the items list and update count.
    # The pre-modification snapshot above is the only recovery path (--rollback).
    if deletions:
        del_set = {str(d) for d in deletions}
        before = len(data['items'])
        deleted_titles = [str(it.get('title', f'#{it.get("num")}'))
                          for it in data['items'] if str(it.get('num')) in del_set]
        data['items'] = [it for it in data['items'] if str(it.get('num')) not in del_set]
        data['count'] = len(data['items'])
        summary['deletions'] = before - len(data['items'])
        print(f'  DELETED {summary["deletions"]} items (nums: {", ".join(sorted(del_set, key=int))})')
        for t in deleted_titles[:5]:
            print(f'    - {t}')
        if len(deleted_titles) > 5:
            print(f'    ... and {len(deleted_titles) - 5} more')

    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nWROTE  {data_path.relative_to(ROOT)}')
    print(f'\nSummary: {summary["date_changes"]} dates · {summary["status_changes"]} statuses · {summary["copy_changes"]} copies · {summary["deletions"]} deletions')
    if summary['missing']:
        print(f'WARN:  skipped items not found in data.json: {", ".join(summary["missing"])}')
    print('\nNext step: rebuild the gantt:')
    print(f'  python build.py --data {data_path.relative_to(ROOT)} --logo assets/logo.png \\')
    print(f'                  --out docs/{slug}/index.html --mode <zeliger|uria>')
    return summary


def rollback(slug: str, snapshot_name: str = None) -> None:
    snaps = list_snapshots(slug)
    if not snaps:
        raise SystemExit('ERROR: no snapshots found')
    if snapshot_name:
        target = snapshots_dir(slug) / snapshot_name
        if not target.exists():
            raise SystemExit(f'ERROR: snapshot not found: {target}')
    else:
        target = snaps[-1]
    data_path = PILOTS / slug / 'data.json'
    # Backup current as a pre-rollback snapshot
    take_snapshot(slug, data_path)
    shutil.copy2(target, data_path)
    print(f'ROLLBACK  {data_path.relative_to(ROOT)} ← {target.relative_to(ROOT)}')
    print('Next step: rebuild the gantt.')


def main():
    p = argparse.ArgumentParser(description='Apply publish payload / snapshot / rollback for gantt-viewer.')
    p.add_argument('--slug', required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--payload', type=Path, help='Path to the JSON exported by the browser "פרסם שינויים" button')
    g.add_argument('--rollback', nargs='?', const='', help='Rollback to a snapshot (latest if no name given)')
    g.add_argument('--list-snapshots', action='store_true')
    args = p.parse_args()

    if args.payload:
        apply_changes(args.slug, args.payload)
    elif args.rollback is not None:
        rollback(args.slug, args.rollback or None)
    elif args.list_snapshots:
        for s in list_snapshots(args.slug):
            print(s.relative_to(ROOT))


if __name__ == '__main__':
    main()
