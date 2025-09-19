#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import argparse
from pathlib import Path
from typing import Optional

import ijson


def split_json_array_file(
    input_path: Path,
    chunk_size: int = 1000,
    out_prefix: str = "your_data_all_answer_",
) -> int:
    if not input_path.exists():
        print(f"[Skip] Input not found: {input_path}")
        return 0

    parent = input_path.parent
    created = 0
    batch_idx = 1

    writer = None  # type: Optional[open]
    is_first_in_current_chunk = True  # Control the comma in writing

    def open_new_writer(idx: int):
        nonlocal writer, is_first_in_current_chunk
        out_path = parent / f"{out_prefix}{idx}.json"
        # Always overwrite: open in write mode
        if writer:
            writer.close()
        writer = open(out_path, "w", encoding="utf-8")
        writer.write("[\n")
        is_first_in_current_chunk = True
        print(f"[Start] {input_path.name} -> {out_path.name} (overwrite)")
        return out_path

    def close_writer_final():
        nonlocal writer
        if writer:
            writer.write("\n]\n")
            writer.close()
            writer = None

    try:
        with open(input_path, "rb") as f:
            count_in_batch = 0

            for obj in ijson.items(f, "item"):
                if writer is None or count_in_batch >= chunk_size:
                    close_writer_final()
                    open_new_writer(batch_idx)
                    created += 1
                    batch_idx += 1
                    count_in_batch = 0
                    is_first_in_current_chunk = True

                if not is_first_in_current_chunk:
                    writer.write(",\n")
                writer.write(json.dumps(obj, ensure_ascii=False, indent=2))
                is_first_in_current_chunk = False
                count_in_batch += 1

        close_writer_final()

        print(f"[Done] Split '{input_path.name}' into {created} file(s) with chunk_size={chunk_size} (overwrite)")
        return created

    except Exception as e:
        close_writer_final()
        print(f"[Error] Failed to split {input_path}: {e}")
        return created


def main():
    parser = argparse.ArgumentParser(
        description="Split large JSON arrays into multiple files by chunk size (streaming with ijson), always overwriting existing outputs."
    )
    parser.add_argument(
        "--root",
        type=str,
        default="your_base_url",
        help="Root directory containing per-model subfolders.",
    )
    parser.add_argument(
        "--input-name",
        type=str,
        default="your_data_all_answer",
        help="Input JSON filename inside each model folder.",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="your_data_all_answer_",
        help="Output filename prefix. Files are named as <prefix>1.json, <prefix>2.json, ...",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Number of objects per output file (default: 1000).",
    )

    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists() or not root.is_dir():
        print(f"[Error] Root not found or not a directory: {root}")
        raise SystemExit(1)

    model_dirs = [p for p in sorted(root.iterdir()) if p.is_dir()]
    if not model_dirs:
        print(f"[Info] No model directories found under: {root}")
        return

    print(f"[Info] Found {len(model_dirs)} model directory(ies) under: {root}")
    print(f"[Info] Input file name: {args.input_name}")
    print(f"[Info] Chunk size: {args.chunk_size}")
    print(f"[Info] Overwrite: True (always overwrite)")

    total_models = 0
    total_outputs = 0

    for mdir in model_dirs:
        input_path = mdir / args.input_name
        if not input_path.exists():
            print(f"[Skip] {mdir.name}: missing {args.input_name}")
            continue

        print(f"[Process] {mdir.name}: splitting {args.input_name}")
        num_created = split_json_array_file(
            input_path=input_path,
            chunk_size=args.chunk_size,
            out_prefix=args.prefix,
        )
        if num_created > 0:
            total_models += 1
            total_outputs += num_created

    print(f"[Summary] Models processed: {total_models}, Split files created: {total_outputs} (overwritten if existed)")


if __name__ == "__main__":
    main()