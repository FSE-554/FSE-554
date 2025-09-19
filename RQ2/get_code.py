#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import sys
import argparse
from typing import List, Dict, Any, Optional, Tuple


# Regular expression pattern for extracting C code blocks
CODE_PATTERN = re.compile(
    r'```c(.*?)```',
    flags=re.DOTALL
)

def load_json_array(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"File {path} is not a JSON array.")
    return data

def extract_code_strict(input_text: str) -> Optional[str]:
    if not isinstance(input_text, str):
        return None
    m = CODE_PATTERN.search(input_text)
    if not m:
        return None
    code = m.group(1).strip() 
    return code

def process_model_dir(
    first_arr: List[Dict[str, Any]],
    model_dir: str,
    combined_name: str = "your_first_file",
    output_name: str = "your_out_put_file_name",
    fail_on_missing: bool = False
) -> Tuple[str, int, int]:

    second_file = os.path.join(model_dir, combined_name)
    output_file = os.path.join(model_dir, output_name)

    if not os.path.exists(second_file):
        return (model_dir, 0, 0)  

    second_arr = load_json_array(second_file)

    if len(second_arr) > len(first_arr):
        raise ValueError(
            f"[{model_dir}] Array length mismatch: {len(second_arr)} (second) cannot exceed {len(first_arr)} (first)"
        )

    merged = []
    missing = 0

    for idx, obj2 in enumerate(second_arr):
        if idx >= len(first_arr):
            break
        
        obj1 = first_arr[idx]
        
        if "input" not in obj1:
            if fail_on_missing:
                raise ValueError(f"[{model_dir}][Index {idx}] Missing 'input' in first file object.")
            origin_code = ""
            missing += 1
        else:
            origin_code = extract_code_strict(obj1["input"])
            if origin_code is None:
                if fail_on_missing:
                    raise ValueError(f"[{model_dir}][Index {idx}] Code block not found in 'input'.")
                origin_code = ""
                missing += 1

        item = dict(obj2) 
        item["origin_code"] = origin_code
        merged.append(item)

    os.makedirs(model_dir, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    return (model_dir, len(merged), missing)

def main() -> None:
    parser = argparse.ArgumentParser(description="Process JSON files for code patching.")
    parser.add_argument("--first_file", type=str, required=True, help="Path to the first JSON file")
    parser.add_argument("--results_root", type=str, required=True, help="Root directory for results")
    parser.add_argument("--combined_name", type=str, default="your_first_file", help="Name of the combined JSON file in model directory")
    parser.add_argument("--output_name", type=str, default="your_out_put_file_name", help="Output JSON file name")
    
    args = parser.parse_args()

    try:
        first_arr = load_json_array(args.first_file)
    except Exception as e:
        print(f"ERROR: Failed to load first file: {args.first_file}\n{e}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.results_root):
        print(f"ERROR: RESULTS_ROOT not found: {args.results_root}", file=sys.stderr)
        sys.exit(1)

    model_dirs = [
        os.path.join(args.results_root, d)
        for d in os.listdir(args.results_root)
        if os.path.isdir(os.path.join(args.results_root, d))
    ]
    model_dirs.sort()

    total_models = 0
    total_items = 0
    total_missing = 0

    for model_dir in model_dirs:
        try:
            mdir, count, missing = process_model_dir(
                first_arr=first_arr,
                model_dir=model_dir,
                combined_name=args.combined_name,
                output_name=args.output_name,
                fail_on_missing=False 
            )
            if count > 0:
                total_models += 1
                total_items += count
                total_missing += missing
                print(f"[OK] {mdir}: wrote {count} items, missing={missing}")
            else:
                print(f"[SKIP] {mdir}: no combined.json")
        except Exception as e:
            print(f"[FAIL] {model_dir}: {e}", file=sys.stderr)

    print("\nSummary:")
    print(f"- Models processed: {total_models}")
    print(f"- Items written:    {total_items}")
    print(f"- Missing matches:  {total_missing}")

if __name__ == "__main__":
    main()