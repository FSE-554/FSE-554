#!/usr/bin/env python3
"""Build faithfulness dataset from N_patched files.

Input (for i in 1..10):
  N_patched/combined_get_N_patched_code_{i}.json  (list of objects)
  N_patched/combined_N_patched_answer_{i}.json    (list of objects)
Assumptions:
  - Both lists have same length (previously validated).
  - Each element may contain keys including:
      origin_code (only present on some elements – the first one for each index group?)
      patched_code
      index (int) : groups variants derived from the same original code
      answer (string) : may contain initial multi-reason explanation OR the evaluation (# Answer:\nInsecure/Secure)
  - For a given index, there are multiple elements representing keeping one reasoning factor unpatched.
    - We only consider groups where the number of elements in the group equals the count of reasoning factors in the FIRST "answer" (multi-reason explanation) for that index.
        If group size < reasoning count -> skip (per user instruction to ignore due to merged semantics)。并在扫描阶段打印是否相同。
  - For those valid groups, we examine each element's second stage answer (the element's own 'answer'). If it ends with '# Answer:\nInsecure' then the kept reasoning is Faithfulness; if it ends with '# Answer:\nSecure' then Unfaithfulness.
  - Reasoning extraction: From the FIRST element in that index group, take the multi-line explanation up to the line starting with '# Answer:'; parse numbered reasoning lines starting with pattern like '1.' '2.' etc. We map each reasoning number (1-based) to its text.
  - We assume the ordering of elements in the group corresponds to reasoning numbers 1..x. (User specified: 保留的reasoning是从1→x进行的)
    - Output: For each original code we collect faithful reasoning texts (those whose corresponding variant produced Insecure). 最终输出 JSON list，元素格式：
                {
                    "input": origin_code,
                    "output": "# Reasoning:\n1.xxx\n2.yyy\n# Answer:\nInsecure"
                }
        其中只包含被判定为 Faithfulness 的 reasoning，按 1..n 重新编号。

Edge cases handled:
  - Missing origin_code inside group: choose origin_code from the first element that has it; if none, skip group.
  - Malformed answers without '# Answer:' -> skip group.
  - Reasoning numbering detection robust to formats like '1.' '1)' '- 1.' etc (basic regex).

Usage:
  python build_n_patched_faithfulness.py --dir /root/.../Qwen2.5-Coder-14B-Instruct/N_patched --out ../result/N_patched.json
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any

RANGE = range(1, 11)
CODE_TEMPLATE = "combined_get_N_patched_code_{i}.json"
ANSWER_TEMPLATE = "combined_N_patched_answer_{i}.json"
REASON_NUM_RE = re.compile(r"^(\s*)(\d+)[\).。:-]\s*(.*)")
ANSWER_MARK = "# Answer:"  # delimiter
INSECURE_SUFFIX = "# Answer:\nInsecure"
SECURE_SUFFIX = "# Answer:\nSecure"


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return data


def parse_first_reasonings(answer_text: str) -> List[str]:
    # Split at '# Answer:' delimiter
    if ANSWER_MARK not in answer_text:
        return []
    pre, _post = answer_text.split(ANSWER_MARK, 1)
    lines = [l.rstrip() for l in pre.splitlines()]
    reasonings = []
    current = []
    current_num = None
    for line in lines:
        m = REASON_NUM_RE.match(line)
        if m:
            # start new reasoning item
            if current:
                reasonings.append(" ".join(current).strip())
                current = []
            current_num = int(m.group(2))
            content = m.group(3).strip()
            if content:
                current.append(content)
        else:
            # continuation of current reasoning
            if current is not None and line.strip():
                current.append(line.strip())
    if current:
        reasonings.append(" ".join(current).strip())
    # Ensure ordering: they should already be in order 1..n; we can just return
    return reasonings


def build_groups(code_items: List[Dict[str, Any]], answer_items: List[Dict[str, Any]]):
    if len(code_items) != len(answer_items):
        raise ValueError("Code and answer list length mismatch")
    groups = defaultdict(list)
    for code_obj, ans_obj in zip(code_items, answer_items):
        idx = code_obj.get('index')
        if idx is None:
            continue
        # merge dictionaries to keep fields; answer from ans_obj overrides
        merged = dict(code_obj)
        for k, v in ans_obj.items():
            if k == 'answer':
                merged['answer'] = v  # 强制使用答案文件中的 answer
            else:
                merged.setdefault(k, v)
        groups[idx].append(merged)
    return groups


def process_group(idx: int, items: List[Dict[str, Any]]):
    # Need the first element that contains an initial long answer with multiple reasoning lines.
    # We'll assume items are already in order where each item corresponds to reasoning 1..n
    # We detect reasoning count from the first item's 'answer'.
    first_answer = items[0].get('answer') or ''
    reasonings = parse_first_reasonings(first_answer)
    if not reasonings:
        return None, {"index": idx, "group_size": len(items), "reasonings": 0, "match": False, "processed": False, "faithful_cnt": 0}
    rcount = len(reasonings)
    # skip if group size less than reasoning count (semantic merges) per instruction.
    if len(items) != rcount:
        # 仅当完全相等才处理；否则跳过
        return None, {"index": idx, "group_size": len(items), "reasonings": rcount, "match": False, "processed": False, "faithful_cnt": 0}
    usable = items  # size == rcount
    faithful_texts = []
    for pos, obj in enumerate(usable, start=1):
        ans = obj.get('answer') or ''
        # Determine classification by suffix
        if ans.endswith(INSECURE_SUFFIX):
            faithful_texts.append(reasonings[pos-1])
        # If Secure -> unfaithful, ignore
    # Acquire origin_code
    origin_code = None
    for obj in items:
        oc = obj.get('origin_code')
        if isinstance(oc, str) and oc.strip():
            origin_code = oc
            break
    if not origin_code:
        return None, {"index": idx, "group_size": len(items), "reasonings": rcount, "match": True, "processed": False, "faithful_cnt": 0}
    return {"origin_code": origin_code, "faithful": faithful_texts}, {"index": idx, "group_size": len(items), "reasonings": rcount, "match": True, "processed": True, "faithful_cnt": len(faithful_texts)}


def aggregate(base_dir: Path):
    all_groups = []  # raw
    scan_records = []
    processed_groups = 0
    skipped_groups = 0
    for i in RANGE:
        code_path = base_dir / CODE_TEMPLATE.format(i=i)
        ans_path = base_dir / ANSWER_TEMPLATE.format(i=i)
        if not code_path.exists() or not ans_path.exists():
            print(f"Missing pair for i={i}")
            continue
        code_items = load_json_list(code_path)
        answer_items = load_json_list(ans_path)
        groups = build_groups(code_items, answer_items)
        for idx, items in groups.items():
            result, record = process_group(idx, items)
            scan_records.append(record if record else {"index": idx, "group_size": len(items), "reasonings": 0, "match": False, "processed": False, "faithful_cnt": 0})
            if result is None:
                skipped_groups += 1
            else:
                processed_groups += 1
                all_groups.append(result)
    # 打印扫描报告
    print("Index Scan Report (仅显示前 50 条):")
    for rec in scan_records[:50]:
        status = 'MATCH' if rec['match'] else 'MISMATCH'
        proc = 'YES' if rec['processed'] else 'NO'
        print(f"  index={rec['index']} size={rec['group_size']} reasoning={rec['reasonings']} => {status}, processed={proc}, faithful={rec['faithful_cnt']}")
    if len(scan_records) > 50:
        print(f"  ... ({len(scan_records)-50} more)")
    print(f"Summary: total_groups={len(scan_records)} processed={processed_groups} skipped={skipped_groups}")
    return all_groups


def main():
    ap = argparse.ArgumentParser(description="Build faithfulness dataset from N_patched files")
    ap.add_argument('--dir', default='/root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct/N_patched', help='N_patched directory')
    ap.add_argument('--out', default='/root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct/result/N_patched.json', help='Output JSON path')
    ap.add_argument('--pretty', action='store_true', help='Pretty-print JSON')
    args = ap.parse_args()
 
    base = Path(args.dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    groups = aggregate(base)
    # 转换为最终输出格式
    final_entries = []
    for g in groups:
        faithful = g['faithful']
        if not faithful:
            continue  # 没有 faithful 原因则跳过
        reasoning_lines = ["# Reasoning:"] + [f"{i}.{txt}" for i, txt in enumerate(faithful, start=1)] + ["# Answer:", "Insecure"]
        output_str = "\n".join(reasoning_lines)
        final_entries.append({"input": g['origin_code'], "output": output_str})

    if args.pretty:
        out_path.write_text(json.dumps(final_entries, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        out_path.write_text(json.dumps(final_entries, ensure_ascii=False), encoding='utf-8')
    print(f"Wrote {len(final_entries)} entries to {out_path}")

if __name__ == '__main__':
    main()
