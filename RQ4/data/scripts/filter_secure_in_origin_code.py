#!/usr/bin/env python3
"""Filter out objects whose 'answer' field ends with '# Answer:\nSecure' in combined_get_origin_code_{i}.json.

Scope: /root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct/full_patched for i in 1..10
Keeps everything else. Writes cleaned file to the same name (in-place) after creating a backup *.bak once.
Supports dry-run by default. Use --apply to modify.

Counting logic: Expects each file to be a JSON array. If not, attempts to load line-delimited JSON.
Elements with missing 'answer' are always kept.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

RANGE = range(1, 11)
FILENAME_TEMPLATE = "combined_get_origin_code_{i}.json"
TARGET_SUFFIX = "# Answer:\nSecure"


def load_items(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data  # assume list of dicts
        # If dict with key 'data'
        if isinstance(data, dict) and isinstance(data.get('data'), list):
            return data['data']
        raise ValueError("Unsupported JSON structure (expected list or dict with data list)")
    except json.JSONDecodeError:
        # try json lines
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                items.append(obj)
            except json.JSONDecodeError:
                pass
        return items


def backup_once(path: Path):
    bak = path.with_suffix(path.suffix + '.bak')
    if not bak.exists():
        bak.write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
        print(f"Backup created: {bak.name}")


def filter_items(items: List[Dict[str, Any]]):
    kept = []
    removed = []
    for obj in items:
        ans = obj.get('answer')
        if isinstance(ans, str) and ans.endswith(TARGET_SUFFIX):
            removed.append(obj)
        else:
            kept.append(obj)
    return kept, removed


def process_file(path: Path, apply: bool):
    items = load_items(path)
    kept, removed = filter_items(items)
    print(f"{path.name}: total={len(items)} remove={len(removed)} keep={len(kept)}")
    if apply and removed:
        backup_once(path)
        # write pretty compact
        path.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"Written filtered file: {path.name}")


def main():
    parser = argparse.ArgumentParser(description="Filter out Secure-ending answers from origin code JSON files")
    parser.add_argument('--dir', default='/root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct/full_patched', help='Full patched directory')
    parser.add_argument('--apply', action='store_true', help='Apply changes in place')
    parser.add_argument('--only', type=int, nargs='*', help='Optional list of i indices to process (default 1..10)')
    args = parser.parse_args()

    base = Path(args.dir)
    indices = args.only if args.only else list(RANGE)
    for i in indices:
        file_path = base / FILENAME_TEMPLATE.format(i=i)
        if not file_path.exists():
            print(f"Missing file: {file_path.name}")
            continue
        process_file(file_path, apply=args.apply)

    if not args.apply:
        print("Dry-run complete. Use --apply to modify files.")

if __name__ == '__main__':
    main()
