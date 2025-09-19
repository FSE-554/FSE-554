#!/usr/bin/env python3
"""Build faithfulness dataset from full_patched files.

For i in 1..10:
  combined_get_origin_code_{i}.json (list of elements with origin_code, etc.)
  combined_full_patched_answer_{i}.json (list with 'answer')
They are 1-1 aligned by position.

Rule:
  If answer ends with '# Answer:\nSecure' => treat ALL reasoning items in that answer as Faithfulness.
  (Else Unfaithfulness, skip.)

Output entry structure:
  {
    "input": <origin_code>,
    "output": "# Reasoning:\n<enumerated faithful reasoning lines>\n# Answer:\nInsecure"
  }

Reasoning extraction: from answer text before the '# Answer:' delimiter, parse numbered lines.
If cannot parse any reasoning, skip.

Writes aggregated list to result/full_patched.json.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Any

RANGE = range(1, 11)
ORIGIN_TEMPLATE = "combined_get_origin_code_{i}.json"
ANSWER_TEMPLATE = "combined_full_patched_answer_{i}.json"
ANSWER_MARK = "# Answer:"
SECURE_SUFFIX = "# Answer:\nSecure"
REASON_NUM_RE = re.compile(r"^(\s*)(\d+)[\).。:-]\s*(.*)")


def load_json_list(path: Path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return data


def parse_reasonings(answer_text: str) -> List[str]:
    if ANSWER_MARK not in answer_text:
        return []
    pre, _ = answer_text.split(ANSWER_MARK, 1)
    lines = [l.rstrip() for l in pre.splitlines()]
    reasonings = []
    current = []
    for line in lines:
        m = REASON_NUM_RE.match(line)
        if m:
            if current:
                reasonings.append(" ".join(current).strip())
                current = []
            content = m.group(3).strip()
            if content:
                current.append(content)
        else:
            if current and line.strip():
                current.append(line.strip())
    if current:
        reasonings.append(" ".join(current).strip())
    return reasonings


def build_entries(base_dir: Path):
    entries = []
    total_pairs = 0
    kept = 0
    skipped_no_secure = 0
    skipped_parse = 0
    for i in RANGE:
        o_path = base_dir / ORIGIN_TEMPLATE.format(i=i)
        a_path = base_dir / ANSWER_TEMPLATE.format(i=i)
        if not (o_path.exists() and a_path.exists()):
            print(f"Missing files for i={i}")
            continue
        origins = load_json_list(o_path)
        answers = load_json_list(a_path)
        if len(origins) != len(answers):
            print(f"Length mismatch i={i}: {len(origins)} vs {len(answers)}")
        for pos, (oc, ans_obj) in enumerate(zip(origins, answers)):
            total_pairs += 1
            answer_text = ans_obj.get('answer', '')
            if not answer_text.endswith(SECURE_SUFFIX):
                skipped_no_secure += 1
                continue
            rs = parse_reasonings(answer_text)
            if not rs:
                skipped_parse += 1
                continue
            origin_code = oc.get('origin_code') or ans_obj.get('origin_code')
            if not origin_code:
                skipped_parse += 1
                continue
            # Build output reasoning block enumerated 1..n
            lines = ["# Reasoning:"]
            for idx, r in enumerate(rs, start=1):
                lines.append(f"{idx}. {r}")
            lines.append("# Answer:\nInsecure")  # Force Insecure per spec
            output_block = "\n".join(lines)
            entries.append({
                "input": origin_code,
                "output": output_block
            })
            kept += 1
    print(f"Pairs processed={total_pairs} kept={kept} skipped_no_secure={skipped_no_secure} skipped_parse={skipped_parse}")
    return entries


def main():
    ap = argparse.ArgumentParser(description="Build full_patched faithfulness dataset")
    ap.add_argument('--dir', default='/root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct/full_patched', help='full_patched directory')
    ap.add_argument('--out', default='/root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct/result/full_patched.json', help='Output path')
    ap.add_argument('--pretty', action='store_true')
    args = ap.parse_args()

    base = Path(args.dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    entries = build_entries(base)
    if args.pretty:
        out_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        out_path.write_text(json.dumps(entries, ensure_ascii=False), encoding='utf-8')
    print(f"Wrote {len(entries)} entries -> {out_path}")

if __name__ == '__main__':
    main()
