#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import re
import json
import logging
import argparse
from typing import List, Dict, Optional

import requests
import ijson

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("runner-server-client")

SERVER_BASE_URL = "http://127.0.0.1:8000/v1"
HEALTH_URL = "http://127.0.0.1:8000/health"
API_KEY = "EMPTY"

SERVED_MODEL_NAME = "your_lora_model_name"

MODELS: Dict[str, str] = {
    "your_lora_model_name": SERVED_MODEL_NAME
}

# Initialize parameters to None
COMBINED_DATASET = None
OUT_PUT = None
BASE_OUTPUT_DIR = None

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

def read_limited_json_array(path: str, limit: int) -> List[Dict]:
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for obj in ijson.items(f, "item"):
            if isinstance(obj, dict) and isinstance(obj.get("input"), str):
                data.append(obj)
                if len(data) >= limit: 
                    break
    return data

def extract_code_from_input(input_field: str) -> Optional[str]:
    if not isinstance(input_field, str):
        return None
    text = input_field.strip()

    m = re.search(r"```c\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if m and m.group(1).strip():
        return m.group(1).strip()

    m = re.search(r"```c(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m and m.group(1).strip():
        return m.group(1).strip()

    return text if text else None

def build_messages_from_code(code: str):
    system = SYSTEM_PROMPT.strip()
    user = (
        "Here is the source code to analyze:\n"
        "```c\n" + code.strip() + "\n```\n"
        "Follow the example format strictly and do not output any additional content.\n"
        "# Reasoning: [Provide your detailed step-by-step analysis using numbered steps: 1., 2., 3., etc.]\n"
        "# Answer:\n['Secure' or 'Insecure']"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

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

def smoke_test_server() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        return r.status_code == 200 
    except Exception:
        logger.exception("[SMOKE TEST] Health check failed")
        return False

def chat_complete(messages, temperature=0.0, top_p=0.9, max_tokens=2048, use_lora=True) -> str:
    url = f"{SERVER_BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    body = {
        "model": SERVED_MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    if use_lora:
        body["lora_modules"] = ["my-lora"]
    resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"] or ""

def run_with_server(data: List[Dict], model_name: str):
    results = [] 
    for index, row 在 enumerate(data):
        code = extract_code_from_input(row["input"]) or "int main(void){return 0;}"
        messages = build_messages_from_code(code)
        text = chat_complete(messages, temperature=0.0, top_p=0.9, max_tokens=2048, use_lora=True)
        trimmed = validate_and_trim_strict(text)
        
        results.append({"answer": trimmed})

    out_dir = os.path.join(BASE_OUTPUT_DIR, model_name)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path。join(out_dir, OUT_PUT)  # Combine output directory and output filename

    with open(out_path, "w", encoding="utf-8") as f: 
        json.dump(results, f, ensure_ascii=False, indent=2)

def main():
    global COMBINED_DATASET, OUT_PUT, BASE_OUTPUT_DIR  # Declare globals to modify those variables

    # Add argument parsing for command-line parameters
    parser = argparse.ArgumentParser(description="Run static code analysis with external parameters.")
    parser.add_argument("combined_dataset", type=str, help="Path to the combined dataset.")
    parser.add_argument("base_output_dir", type=str, help="Base output directory for results.")
    parser.add_argument("output_filename", type=str, help="Output filename for results.")
    args = parser.parse_args()

    # Set the parameters from command-line arguments
    COMBINED_DATASET = args.combined_dataset
    BASE_OUTPUT_DIR = args.base_output_dir
    OUT_PUT = args.output_filename  # Update output filename based on argument

    if not smoke_test_server():
        logger.error("Server health check failed. Please ensure vLLM serve is running.")
        return

    logger.info(f"Loading dataset from {COMBINED_DATASET}")
    data = read_limited_json_array(COMBINED_DATASET, float('inf')) 
    logger.info(f"Loaded {len(data)} items")

    for model_key, served_name in MODELS.items():
        logger.info("=" * 80)
        logger.info(f"Model [{model_key}] via service name [{served_name}]")
        try:
            run_with_server(data, model_key) 
            logger.info(f"[{model_key}] Processed {len(data)} records.")
        except Exception as e:
            logger.exception(f"[{model_key}] Inference failed: {e}")

    logger.info("Done.")

if __name__ == "__main__":
    main()
