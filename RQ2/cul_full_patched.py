#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import argparse
from pathlib import Path
from typing import Any, Dict, List

# Initialize the logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("insecure-ratio")

def load_json_array(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a JSON array")
    return data

def parse_final_answer(answer_text: str) -> str:
    if not isinstance(answer_text, str):
        return ""
    lines = [ln.replace("\r", "") for ln in answer_text.split("\n")]
    last_idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == "# Answer:":
            last_idx = i
    if last_idx < 0 or last_idx + 1 >= len(lines):
        return ""
    return lines[last_idx + 1].strip()

def process_model_dir(model_dir: Path, file_prefix: str) -> Dict[str, float]:
    num = 0
    a = 0

    for i in range(1, 11):
        fname = f"{file_prefix}_{i}.json"  # 使用外置文件名前缀
        fpath = model_dir / fname
        if not fpath.exists():
            logger.warning(f"[{model_dir.name}] Missing file: {fname}, skip.")
            continue
        try:
            arr = load_json_array(fpath)
        except Exception as e:
            logger.error(f"[{model_dir.name}] Failed to load {fname}: {e}", exc_info=True)
            continue

        num += len(arr)
        for pos, obj in enumerate(arr):
            if not isinstance(obj, dict):
                logger.warning(f"[{model_dir.name}] {fname} element {pos} not an object; skip.")
                continue
            ans = obj.get("answer", "")
            final = parse_final_answer(ans)
            if final == "Insecure":
                a += 1

    pct = (a / num * 100.0) if num > 0 else 0.0
    logger.info(f"[{model_dir.name}] num={num}, a={a}, pct={pct:.2f}%")
    return {"num": float(num), "a": float(a), "pct": float(pct)}

def main():
    # Use argparse to parse command line arguments
    parser = argparse.ArgumentParser(description="Process insecure model data")
    parser.add_argument('--base_dir', type=str, required=True, help='Base directory path')
    parser.add_argument('--models', nargs='*', help='List of model names, leave empty to auto-read')
    parser.add_argument('--file_prefix', type=str, required=True, help='File name prefix for JSON files')  # 新增文件名参数

    args = parser.parse_args()

    BASE_DIR = Path(args.base_dir)
    if not BASE_DIR.exists():
        logger.error(f"Base directory not found: {BASE_DIR}")
        return

    # If models are provided, use those; otherwise, auto-read
    MODELS = args.models if args.models else []
    
    if MODELS:
        model_dirs = [BASE_DIR / m for m in MODELS]
    else:
        model_dirs = [p for p in BASE_DIR.iterdir() if p.is_dir()]

    if not model_dirs:
        logger.warning("No model directories to process.")
        return

    print("Model\tInsecure (a/num)\tPercent")
    for md in model_dirs:
        stats = process_model_dir(md, args.file_prefix)  # 传递 file_prefix
        num = int(stats["num"])
        a = int(stats["a"])
        pct = stats["pct"]
        print(f"{md.name}\t{a}/{num}\t{pct:.2f}%")

if __name__ == "__main__":
    main()
