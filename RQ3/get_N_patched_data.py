import os  
import json  
from pathlib import Path  
from typing import List, Dict, Any, Union  
import argparse

# Declare global variables for parameters
BASE_DIR: Path  
INPUT_FILENAME: str  
OUTPUT_FILENAME: str

def wrap_c_code_block(code: str) -> str:  
    code = "" if code is None else str(code)  
    return f"```c\n{code}\n```"  

def normalize_items(data: Any) -> List[Dict[str, Any]]:  
    if isinstance(data, list):  
        return [x for x in data if isinstance(x, dict)]  
    elif isinstance(data, dict):  
        for k in ("data", "items", "records", "results"):  
            if k in data and isinstance(data[k], list):  
                return [x for x in data[k] if isinstance(x, dict)]   
        return [data]  
    else:  
        return []  

def extract_patched_entries(items: List[Dict[str, Any]]) -> List[Dict[str, str]]:  
    outputs: List[Dict[str, str]] = []  
    for idx, rec in enumerate(items):  
        if "patched_code" not in rec:  
            continue  
        pc = rec["patched_code"]  
        if isinstance(pc, list):  
            for seg in pc:  
                outputs.append({"input": wrap_c_code_block(seg)})  
        else:  
            outputs.append({"input": wrap_c_code_block(pc)})  
    return outputs  

def process_model_dir(model_dir: Path) -> None:  
    in_path = model_dir / INPUT_FILENAME  
    out_path = model_dir / OUTPUT_FILENAME  

    if not in_path.exists():  
        print(f"[Skip] {in_path} does not exist. Skipping.")  
        return  

    try:  
        with open(in_path, "r", encoding="utf-8") as f:  
            data = json.load(f)  
    except Exception as e:  
        print(f"[Error] Failed to read {in_path}: {e}")  
        return  

    items = normalize_items(data)  
    if not items:  
        print(f"[Warn] Unable to parse JSON format to a list of records from {in_path}, skipping.")  
        return  

    out_recs = extract_patched_entries(items)  
    if not out_recs:  
        print(f"[Warn] No 'patched_code' fields found in {in_path}, skipping.")  
        return  

    try:  
        with open(out_path, "w", encoding="utf-8") as f:  
            json.dump(out_recs, f, ensure_ascii=False, indent=2)  
        print(f"[OK] Generated {out_path} ({len(out_recs)} records)")  
    except Exception as e:  
        print(f"[Error] Failed to write {out_path}: {e}")  

def main():  
    global BASE_DIR, INPUT_FILENAME, OUTPUT_FILENAME

    # Argument parsing for external parameters
    parser = argparse.ArgumentParser(description="Process JSON files for C code vulnerabilities")
    parser.add_argument("--base_dir", type=str, required=True, help="Base directory path")
    parser.add_argument("--input_filename", type=str, required=True, help="Input filename")
    parser.add_argument("--output_filename", type=str, required=True, help="Output filename")
    args = parser.parse_args()

    BASE_DIR = Path(args.base_dir)  
    INPUT_FILENAME = args.input_filename  
    OUTPUT_FILENAME = args.output_filename  

    if not BASE_DIR.exists():  
        print(f"[Error] Base directory does not exist: {BASE_DIR}")  
        return  

    for entry in BASE_DIR.iterdir():  
        if entry.is_dir():  
            process_model_dir(entry)  

if __name__ == "__main__":  
    main()  