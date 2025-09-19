#!/usr/bin/env python3
"""Statistic script for Qwen dataset paired JSON counts.

For i in 1..10:
  In N_patched/ compare:
    combined_get_N_patched_code_{i}.json  vs combined_N_patched_answer_{i}.json
  In full_patched/ compare:
    combined_get_origin_code_{i}.json      vs combined_full_patched_answer_{i}.json

Assumptions: Each file is a JSON array OR a JSON lines file OR a plain JSON object with list under key 'data'. We count top-level element objects:
 - If the file parses to a list -> len(list)
 - If parses to a dict and has key 'data' that is a list -> len(dict['data'])
 - Else if parses to a dict -> count its top-level keys (fallback)
 - If it's JSON Lines (one JSON per line) we detect by failure of standard parse then iterate non-empty lines and parse individually.
Prints a summary table and warns mismatches.
"""
from __future__ import annotations
import json
from pathlib import Path
import argparse

RANGE = range(1, 11)

PAIR_SPECS = [
    ("N_patched", "combined_get_N_patched_code_{i}.json", "combined_N_patched_answer_{i}.json"),
    ("full_patched", "combined_get_origin_code_{i}.json", "combined_full_patched_answer_{i}.json"),
]

def count_elements(path: Path) -> int:
    if not path.exists():
        return -1  # sentinel for missing
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        return 0
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try JSON lines
        count = 0
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
                count += 1
            except json.JSONDecodeError:
                # ignore bad line
                pass
        return count
    # Structured parse
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        if isinstance(data.get('data'), list):
            return len(data['data'])
        return len(data)
    return 0

def main():
    ap = argparse.ArgumentParser(description='Check paired JSON element counts for Qwen dataset')
    ap.add_argument('--base', default='/root/students/hebingyi/data/Mistral-7B-Instruct-v0.3', help='Base directory')
    ap.add_argument('--json', action='store_true', help='Output machine-readable JSON')
    args = ap.parse_args()

    base = Path(args.base)
    rows = []
    mismatches = []

    for subdir, pat_a, pat_b in PAIR_SPECS:
        dir_path = base / subdir
        for i in RANGE:
            f_a = dir_path / pat_a.format(i=i)
            f_b = dir_path / pat_b.format(i=i)
            c_a = count_elements(f_a)
            c_b = count_elements(f_b)
            equal = (c_a == c_b) and c_a >= 0
            if not equal:
                mismatches.append((subdir, i, c_a, c_b))
            rows.append({
                'group': subdir,
                'i': i,
                'file_a': f_a.name,
                'count_a': c_a,
                'file_b': f_b.name,
                'count_b': c_b,
                'equal': equal,
            })

    if args.json:
        import json as _json
        print(_json.dumps({'rows': rows, 'mismatches': mismatches}, ensure_ascii=False, indent=2))
        return

    # Human table
    header = f"{'Group':<12}{'i':<4}{'Count A':>10}{'Count B':>10}{'Equal':>8}  File A -> File B"
    print(header)
    print('-'*len(header))
    for r in rows:
        ca = r['count_a']
        cb = r['count_b']
        def fmt(v):
            return 'MISS' if v == -1 else str(v)
        print(f"{r['group']:<12}{r['i']:<4}{fmt(ca):>10}{fmt(cb):>10}{str(r['equal']):>8}  {r['file_a']} | {r['file_b']}")

    if mismatches:
        print(f"\nMISMATCHES ({len(mismatches)}):")
        for subdir, i, ca, cb in mismatches[:20]:
            def fmt(v):
                return 'MISS' if v == -1 else v
            print(f"  {subdir} i={i}: {fmt(ca)} vs {fmt(cb)}")
    else:
        print("\nAll pairs matched.")

if __name__ == '__main__':
    main()
