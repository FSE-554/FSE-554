#!/usr/bin/env python3
"""Prune files in Qwen2.5-Coder-14B-Instruct directory.

Keeps only the following patterns for i in 1..10 (inclusive):
  combined_get_N_patched_code_i.json
  combined_N_patched_answer_i.json
  combined_full_patched_answer_i.json
  combined_get_origin_code_i.json

Everything else in that directory (only top-level files, not subdirs) will be deleted.
A dry-run mode is available.
"""
from __future__ import annotations
import argparse
from pathlib import Path

KEEP_PATTERNS = [
    "combined_get_N_patched_code_{i}.json",
    "combined_N_patched_answer_{i}.json",
    "combined_full_patched_answer_{i}.json",
    "combined_get_origin_code_{i}.json",
]

RANGE = range(1, 11)  # 1..10

def build_whitelist(dir_path: Path) -> set[Path]:
    keep: set[Path] = set()
    for i in RANGE:
        for pat in KEEP_PATTERNS:
            keep.add(dir_path / pat.format(i=i))
    return keep

def prune(dir_path: Path, dry_run: bool = True) -> None:
    if not dir_path.is_dir():
        raise SystemExit(f"Directory not found: {dir_path}")

    whitelist = build_whitelist(dir_path)
    existing_whitelist = {p for p in whitelist if p.exists()}

    deletions = []
    for child in dir_path.iterdir():
        # Skip directories
        if child.is_dir():
            continue
        if child in whitelist:
            continue
        deletions.append(child)

    print(f"Whitelist expected {len(whitelist)} files. Present: {len(existing_whitelist)}")
    missing = whitelist - existing_whitelist
    if missing:
        print(f"Missing {len(missing)} expected files (showing first 20):")
        for p in list(sorted(missing))[:20]:
            print("  MISSING:", p.name)

    if not deletions:
        print("No files to delete.")
        return

    print(f"Will delete {len(deletions)} files (showing first 30):")
    for p in deletions[:30]:
        print("  DELETE:", p.name)
    if len(deletions) > 30:
        print("  ...")

    if dry_run:
        print("Dry-run mode: no files deleted. Use --apply to actually delete.")
        return

    for p in deletions:
        try:
            p.unlink()
        except Exception as e:
            print(f"Failed to delete {p.name}: {e}")
    print("Deletion complete.")


def main():
    parser = argparse.ArgumentParser(description="Prune unwanted JSON files from Qwen directory")
    parser.add_argument("--dir", default="/root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct", help="Target directory")
    parser.add_argument("--apply", action="store_true", help="Actually delete files (otherwise dry-run)")
    args = parser.parse_args()
    prune(Path(args.dir), dry_run=not args.apply)

if __name__ == "__main__":
    main()
