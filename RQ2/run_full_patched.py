#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import ray
import logging
import argparse
from typing import List, Dict, Optional
from packaging.version import Version
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("runner")
logging.getLogger("vllm").setLevel(logging.DEBUG)
logging.getLogger("ray").setLevel(logging.INFO)

import ray as _ray_version_check
assert Version(_ray_version_check.__version__) >= Version("2.44.1"), (
    f"Ray version must be at least 2.44.1, got {_ray_version_check.__version__}"
)

MODELS: Dict[str, str] = {
    "your_model_path"  # Placeholder for model paths; to be populated later
}

# Externalized parameters
BASE_RESULTS_DIR: Path
INPUT_BASENAME: str
OUTPUT_BASENAME: str

SYSTEM_PROMPT = """
You are a world-class security expert specializing in static program analysis. You are meticulous, methodical, and think adversarially. Your goal is to identify any potential weakness, flaw, or violation of security best practices in the provided source code.

-----

### Task

Analyze the given source code snippet to determine if it contains any security vulnerabilities. Your analysis must be thorough, covering common vulnerability classes such as (but not limited to):

  - **Buffer Overflows**: Use of unsafe functions like `strcpy`, `strcat`, `gets`, `sprintf`.
  - **Path Traversal**: Improper handling of file paths from user input.
  - **Integer Overflows/Underflows**: Arithmetic operations on user-controlled data without proper checks.
  - **Format String Vulnerabilities**: Use of user-controlled strings in functions like `printf`, `sprintf`.
  - **Memory Management Issues**: `malloc`/`free` mismatches, use-after-free, double free, memory leaks, and unchecked `malloc` return values.
  - **Unchecked Return Values**: Ignoring the return values of critical functions (e.g., `fopen`, `malloc`).
  - **Race Conditions**: Time-of-check to time-of-use (TOCTOU) flaws.

-----

### Output Format (Strictly Enforced)

Your output **MUST** conform to the following structure precisely. Any deviation will be considered a failure.

1.  **Reasoning Section**:

      - Start with the header `# Reasoning:` exactly as written, on its own line.
      - Following the header, provide your step-by-step analysis as a numbered list (`1.`, `2.`, `3.`, ...).
      - Each point should detail a specific finding or observation about the code's security posture. Be concise but clear.

2.  **Answer Section**:

      - After all reasoning points, include the header `# Answer:` exactly as written, on its own line.
      - On the line **immediately following** `# Answer:`, you must output a **single word**: either `Insecure` or `Secure`.
      - The code is **Insecure** if you find even one plausible vulnerability or a significant deviation from security best practices.
      - The code is **Secure** only if it is free from all identifiable vulnerabilities and follows modern, safe coding standards.

3.  **Final Rule**:

      - **DO NOT** output anything else after the final `Insecure` or `Secure` word. No explanations, no punctuation, no apologies, no concluding sentences.

-----

### Example

**Input Code:**

```c
void write_to_file(char* file_name, char* data)
{
    char* dir = "/home/user/";

    char* full_path = malloc(strlen(dir) + strlen(file_name) + 1);
    strcpy(full_path, dir);
    strcat(full_path, file_name);

    FILE* f = fopen(full_path, "w");
    if (f == NULL) {
        printf("Error opening file: %s\n", file_name);
        return 1;
    }
    else {
        fprintf(f, "%s", data);
    }
    fclose(f);
    free(full_path);
    full_path = NULL;
}
```

Output Example:

```
# Reasoning:
1. The function uses `strcpy` and `strcat`, which are unsafe as they do not perform bounds checking. This can lead to a buffer overflow if `file_name` is unexpectedly large.
2. The return value of `malloc` is not checked. If `malloc` fails and returns `NULL`, the subsequent `strcpy` will cause a crash (segmentation fault).
3. The `file_name` parameter is concatenated directly into the path. An attacker could provide a malicious string like `../../etc/passwd` to write to arbitrary files on the system. This is a classic path traversal vulnerability.
4. The function signature is `void` but it attempts to `return 1;`, which is a compilation error and indicates poor code quality.
5. If `fopen` fails, the allocated memory for `full_path` is not freed, leading to a memory leak.

# Answer:
Insecure
""" 

def read_per_model_inputs(path: Path) -> List[Dict]:
    """读取单个模型目录的 combined_full_patched_test.json（数组，每项包含 input:str）"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must be a list of objects")
    data = [x for x in data if isinstance(x, dict) and isinstance(x.get("input"), str)]
    return data

def print_cuda_info():
    try:
        import torch
        logger.info(f"torch.cuda.is_available(): {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"CUDA: {torch.version.cuda}, GPU count: {torch.cuda.device_count()}")
            logger.info(f"GPU 0: {torch.cuda.get_device_name(0)}")
    except Exception as e:
        logger.warning(f"Failed to query CUDA info: {e}")

def is_supported_by_vllm(model_source: str) -> bool:
    lower = model_source.lower()
    if "gguf" in lower:
        return False
    return True

def extract_code_from_input(input_field: str) -> Optional[str]:
    if not isinstance(input_field, str):
        return None
    text = input_field.strip()

    m = re.search(r"```c\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        if code:
            return code

    m = re.search(r"```c(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        if code:
            return code

    if text:
        return text
    return None

def build_prompt_from_code(code: str) -> str:
    system = SYSTEM_PROMPT.strip()
    user = (
        "Here is the source code to analyze:\n"
        "```c\n" + code.strip() + "\n```\n"
        "Follow the example format strictly and do not output any additional content.\n"
        "# Reasoning: [Provide your detailed step-by-step analysis using numbered steps: 1., 2., 3., etc.]\n"
        "# Answer:\n['Secure' or 'Insecure']"
    )

    return f"System:\n{system}\n\nUser:\n{user}\n\nAssistant:"

def validate_and_trim_strict(text: str) -> str:
    if not text:
        return ""
    t = text.strip()

    if not t.startswith("# Reasoning:"):
        idx_r = t.find("# Reasoning:")
        if idx_r == -1:
            return ""
        t = t[idx_r:].strip()

    idx_ans = t.find("# Answer:")
    if idx_ans == -1:
        return ""

    head = t[:idx_ans].rstrip()
    tail_lines = t[idx_ans:].splitlines()

    ans_idx = None
    for i, ln in enumerate(tail_lines):
        if ln.strip() == "# Answer:":
            ans_idx = i
            break
    if ans_idx is None or ans_idx == len(tail_lines) - 1:
        return ""

    final_word = tail_lines[ans_idx + 1].strip()
    if final_word not in ("Secure", "Insecure"):
        return ""

    answer_header = "\n".join(tail_lines[:ans_idx + 1])
    trimmed = head + "\n" + answer_header + "\n" + final_word
    return trimmed

def coerce_to_template(raw_text: str) -> str:
    lines = [ln.strip() for ln in re.split(r'[\n\r]+', (raw_text or "")) if ln.strip()]
    if not lines:
        lines = ["No explicit reasoning found."]
    bullets = lines[:5]
    reasoning = "\n".join(f"{i+1}. {b}" for i, b in enumerate(bullets))
    return f"# Reasoning:\n{reasoning}\n\n# Answer:\nInsecure"

def run_with_vllm_direct(data: List[Dict], model_source: str) -> List[Dict]:
    from vllm import LLM, SamplingParams

    llm = LLM(
        model=model_source,
        tensor_parallel_size=4,
        dtype="float16",
        enforce_eager=True,
        gpu_memory_utilization=0.80,
        max_model_len=3072,
        enable_chunked_prefill=True,
        trust_remote_code=True,
    )
    sp = SamplingParams(
        temperature=0,              
        top_p=0.9,                     
        max_tokens=3072,              
    )

    prompts = []
    for row in data:
        code = extract_code_from_input(row["input"])
        if not code:
            code = "int main(void){return 0;}"
        prompts.append(build_prompt_from_code(code))

    outputs = llm.generate(prompts, sp)

    results_list: List[Dict] = []
    for out in outputs:
        text = out.outputs[0].text if (out.outputs and len(out.outputs) > 0) else ""
        trimmed = validate_and_trim_strict(text)
        if not trimmed:
            trimmed = coerce_to_template(text)
        results_list.append({"answer": trimmed})

    return results_list

def main():
    # Argument parsing for external parameters
    parser = argparse.ArgumentParser(description="Multi-model batch inference script")
    parser.add_argument("--base_results_dir", type=str, required=True, help="Base directory for results")
    parser.add_argument("--input_basename", type=str, required=True, help="Input file name for each model")
    parser.add_argument("--output_basename", type=str, required=True, help="Output file name for each model")
    args = parser.parse_args()

    # Assign global variables from command-line arguments
    global BASE_RESULTS_DIR, INPUT_BASENAME, OUTPUT_BASENAME
    BASE_RESULTS_DIR = Path(args.base_results_dir)
    INPUT_BASENAME = args.input_basename
    OUTPUT_BASENAME = args.output_basename

    print_cuda_info()

    for model_key, model_source in MODELS.items():
        logger.info("=" * 80)
        logger.info(f"Model [{model_key}] => {model_source}")

        if not is_supported_by_vllm(model_source):
            logger.warning(f"Model [{model_key}] appears unsupported by vLLM (e.g., GGUF). Skipping.")
            continue

        model_dir = BASE_RESULTS_DIR / model_key
        in_path = model_dir / INPUT_BASENAME
        out_path = model_dir / OUTPUT_BASENAME

        if not in_path.exists():
            logger.warning(f"[{model_key}] Input file not found: {in_path}. Skipping this model.")
            continue

        try:
            data = read_per_model_inputs(in_path)
            logger.info(f"[{model_key}] Loaded {len(data)} rows from {in_path.name}")

            results_list = run_with_vllm_direct(data, model_source)

            os.makedirs(model_dir, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(results_list, f, ensure_ascii=False, indent=2)
            logger.info(f"[{model_key}] Wrote JSON to {out_path} (records={len(results_list)})")

        except Exception:
            logger.error(f"[{model_key}] Inference failed.", exc_info=True)
            continue

    logger.info("All models processed. Done.")

if __name__ == "__main__":
    main()