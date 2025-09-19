#!/usr/bin/env python3
"""Organize selected Qwen dataset JSON files into subdirectories.

Moves (for i in 1..10):
  combined_get_N_patched_code_{i}.json
  combined_N_patched_answer_{i}.json          --> N_patched/
  combined_full_patched_answer_{i}.json
  combined_get_origin_code_{i}.json           --> full_patched/

Default target directory: /root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct
Dry-run by default; use --apply to actually move.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Iterable

RANGE = range(1, 11)

GROUPS = {
    "N_patched": [
        "combined_get_N_patched_code_{i}.json",
        "combined_N_patched_answer_{i}.json",
    ],
    "full_patched": [
        "combined_full_patched_answer_{i}.json",
        "combined_get_origin_code_{i}.json",
    ],
}

def generate_moves(base: Path):
    for folder, patterns in GROUPS.items():
        target_dir = base / folder
        for i in RANGE:
            for pat in patterns:
                src = base / pat.format(i=i)
                dst = target_dir / src.name
                yield src, dst

def organize(base_dir: Path, dry_run: bool = True) -> None:
    if not base_dir.is_dir():
        raise SystemExit(f"Directory not found: {base_dir}")

    planned = list(generate_moves(base_dir))
    needed_dirs = sorted({dst.parent for (_, dst) in planned})

    print(f"Planned moves: {len(planned)} files (existing + missing).")

    moves = []
    missing = []
    already_ok = 0
    for src, dst in planned:
        if not src.exists():
            missing.append(src)
            continue
        if dst.exists():
            already_ok += 1
            continue
        moves.append((src, dst))

    for d in needed_dirs:
        if not d.exists():
            print(f"Will create dir: {d}")

    print(f"Files to move: {len(moves)} | Already in place: {already_ok} | Missing: {len(missing)}")
    show = moves[:20]
    if show:
        print("Sample moves (up to 20):")
        for s, d in show:
            print(f"  {s.name} -> {d.parent.name}/")

    if missing:
        print("Missing files (up to 10 shown):")
        for m in missing[:10]:
            print("  MISSING:", m.name)

    if dry_run:
        print("Dry-run mode: no changes applied. Use --apply to perform moves.")
        return

    # Apply
    for d in needed_dirs:
        d.mkdir(parents=True, exist_ok=True)

    moved_count = 0
    for src, dst in moves:
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            moved_count += 1
        except Exception as e:
            print(f"Failed to move {src.name}: {e}")

    print(f"Done. Moved {moved_count} files. ({already_ok} already in place, {len(missing)} missing)")


def main():
    parser = argparse.ArgumentParser(description="Organize Qwen JSON files into grouped subfolders")
    parser.add_argument("--dir", default="/root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct", help="Base directory")
    parser.add_argument("--apply", action="store_true", help="Actually perform moves")
    args = parser.parse_args()
    organize(Path(args.dir), dry_run=not args.apply)

if __name__ == "__main__":
    main()
