#!/usr/bin/env python3
"""Merge N_patched.json and full_patched.json into data_base.json with instruction field."""
from __future__ import annotations
import json
from pathlib import Path

INSTRUCTION = """
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
""".strip()


def load_list(path: Path):
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8') or '[]')
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return data


def normalize_entry(entry):
    # entry may already have input/output, we just add instruction
    return {
        'instruction': INSTRUCTION,
        'input': entry.get('input', ''),
        'output': entry.get('output', ''),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description='Merge full_patched.json and N_patched.json into data_base.json with instruction field.')
    ap.add_argument('--base', default='/root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct/result', help='Result directory containing the two source json files.')
    ap.add_argument('--out', default='/root/students/hebingyi/data/Qwen2.5-Coder-14B-Instruct/data_base.json', help='Output merged json path')
    ap.add_argument('--pretty', action='store_true', help='Pretty print output')
    args = ap.parse_args()

    base_dir = Path(args.base)
    full_path = base_dir / 'full_patched.json'
    n_path = base_dir / 'N_patched.json'

    full_list = load_list(full_path)
    n_list = load_list(n_path)

    merged = [normalize_entry(e) for e in full_list] + [normalize_entry(e) for e in n_list]

    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2 if args.pretty else None),
        encoding='utf-8'
    )
    print(f"Merged {len(full_list)} full_patched + {len(n_list)} N_patched -> {len(merged)} entries -> {out_path}")

if __name__ == '__main__':
    main()
