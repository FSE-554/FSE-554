#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
from pathlib import Path
from typing import List, Dict
import argparse

# ===== Logging =====
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("inject-index")

# Declare global variables for parameters
BASE_DIR: Path = Path()
MODELS: List[str] = []
N_PATCHED_CODE_NAME: str = "your_N_patched_code_{i}.json"  # Template for code file names
N_PATCHED_ANSWER_NAME: str = "your_N_patched_answer_{i}.json"  # Template for answer file names

def load_json_array(path: Path) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a JSON array")
    return data

def save_json_array(path: Path, arr: List[Dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arr, f, ensure_ascii=False, indent=2)

def inject_index_for_pair(code_path: Path, ans_path: Path) -> None:
    code_arr = load_json_array(code_path)
    ans_arr = load_json_array(ans_path)

    min_length = min(len(code_arr), len(ans_arr))

    updated = 0
    for idx in range(min_length):
        code_obj = code_arr[idx]
        ans_obj = ans_arr[idx]
        try:
            if not isinstance(code_obj, dict) or not isinstance(ans_obj, dict):
                raise ValueError(f"Element at position {idx} is not an object in one of the files.")
            if "index" not in code_obj:
                logger.warning(f"Missing 'index' in {code_path.name} at position {idx}; skipping this element.")
                continue
            ans_obj["index"] = code_obj["index"]
            updated += 1
        except Exception as e:
            logger.error(f"Error processing index at position {idx}: {e}")

    save_json_array(ans_path, ans_arr)
    logger.info(f"Updated {updated}/{min_length} items -> {ans_path}")

def process_model_dir(model_dir: Path) -> None:
    for i in range(1, 10):  # Default length of patched files (temporary, can be adjusted later)
        code_name = N_PATCHED_CODE_NAME.format(i=i)
        ans_name  = N_PATCHED_ANSWER_NAME.format(i=i)
        code_path = model_dir / code_name
        ans_path  = model_dir / ans_name

        if not code_path.exists():
            logger.warning(f"[{model_dir.name}] Missing: {code_path.name}, skipping i={i}.")
            continue
        if not ans_path.exists():
            logger.warning(f"[{model_dir.name}] Missing: {ans_path.name}, skipping i={i}.")
            continue

        try:
            inject_index_for_pair(code_path, ans_path)
        except Exception as e:
            logger.error(f"[{model_dir.name}] Failed on i={i}: {e}", exc_info=True)

def main():
    global BASE_DIR, MODELS, N_PATCHED_CODE_NAME, N_PATCHED_ANSWER_NAME

    # Argument parsing for external parameters
    parser = argparse.ArgumentParser(description="Inject index for paired JSON files")
    parser.add_argument("--base_dir", type=str, required=True, help="Base directory path")
    parser.add_argument("--models", nargs='*', help="List of model names (folders)")
    parser.add_argument("--code_name", type=str, default="your_N_patched_code_{i}.json", help="Code filename template")
    parser.add_argument("--answer_name", type=str, default="your_N_patched_answer_{i}.json", help="Answer filename template")
    args = parser.parse_args()

    BASE_DIR = Path(args.base_dir)
    MODELS = args.models if args.models else []
    N_PATCHED_CODE_NAME = args.code_name
    N_PATCHED_ANSWER_NAME = args.answer_name

    if not BASE_DIR.exists():  
        logger.warning(f"[Error] Base directory does not exist: {BASE_DIR}")  
        return  

    model_dirs: List[Path]
    if MODELS:
        model_dirs = [BASE_DIR / m for m in MODELS]
    else:
        model_dirs = [p for p in BASE_DIR.iterdir() if p.is_dir()]

    if not model_dirs:
        logger.warning("No model directories found.")
        return

    for md in model_dirs:
        logger.info(f"Processing model dir: {md}")
        process_model_dir(md)

    logger.info("Done.")

if __name__ == "__main__":  
    main()