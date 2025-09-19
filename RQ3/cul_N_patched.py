#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Any
import argparse

# ===== Logging =====
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("secure-coverage")

# Declare global variables for parameters
BASE_DIR: Path = Path()
MODELS: List[str] = []

def load_json_array(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a JSON array")
    return data

def is_secure_answer(answer_text: str) -> bool:
    if not isinstance(answer_text, str):
        return False
    lines = [ln.replace("\r", "") for ln in answer_text.split("\n")]
    last_idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == "# Answer:":
            last_idx = i
    if last_idx < 0 or last_idx + 1 >= len(lines):
        return False
    return lines[last_idx + 1].strip() == "Secure"

def process_model_dir(model_dir: Path) -> Dict[str, float]:
    all_indices: Set[Any] = set()
    index_has_secure: Dict[Any, bool] = {}

    for i in range(1, 11):
        ans_name = f"your_N_patched_answer_{i}.json"
        ans_path = model_dir / ans_name
        if not ans_path.exists():
            logger.warning(f"[{model_dir.name}] Missing file: {ans_name}, skipping i={i}")
            continue
        try:
            arr = load_json_array(ans_path)
        except Exception as e:
            logger.error(f"[{model_dir.name}] Failed to load {ans_name}: {e}", exc_info=True)
            continue

        for pos, obj in enumerate(arr):
            if not isinstance(obj, dict):
                logger.warning(f"[{model_dir.name}] {ans_name} element {pos} is not an object; skipping.")
                continue
            if "index" not in obj:
                logger.warning(f"[{model_dir.name}] {ans_name} element {pos} missing 'index'; skipping.")
                continue
            idx = obj["index"]
            all_indices.add(idx)

            ans = obj.get("answer", "")
            if is_secure_answer(ans):
                index_has_secure[idx] = True
            else:
                index_has_secure.setdefault(idx, False)

    num = len(all_indices)
    a = sum(1 for v in index_has_secure.values() if v is True)
    pct = (a / num * 100.0) if num > 0 else 0.0

    logger.info(f"[{model_dir.name}] num={num}, a={a}, pct={pct:.2f}%")
    return {"num": float(num), "a": float(a), "pct": float(pct)}

def main():
    global BASE_DIR, MODELS

    # Argument parsing for external parameters
    parser = argparse.ArgumentParser(description="Secure Coverage Checker")
    parser.add_argument("--base_dir", type=str, required=True, help="Base directory path")
    parser.add_argument("--models", nargs='*', help="List of model names (folders)")
    args = parser.parse_args()

    BASE_DIR = Path(args.base_dir)
    MODELS = args.models if args.models else []

    if not BASE_DIR.exists():
        logger.error(f"Base directory not found: {BASE_DIR}")
        return

    if MODELS:
        model_dirs = [BASE_DIR / m for m in MODELS]
    else:
        model_dirs = [p for p in BASE_DIR.iterdir() if p.is_dir()]

    if not model_dirs:
        logger.warning("No model directories to process.")
        return

    print("Model\tCoverage (a/num)\tPercent")
    for md in model_dirs:
        stats = process_model_dir(md)
        num = int(stats["num"])
        a = int(stats["a"])
        pct = stats["pct"]
        print(f"{md.name}\t{a}/{num}\t{pct:.2f}%")

if __name__ == "__main__":
    main()