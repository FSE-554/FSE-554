#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from tqdm import tqdm
import asyncio
import aiohttp
import argparse

logger = logging.getLogger("deepseek_variant_parallel_newio")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

class Prompts:
    VULN_ANALYSIS_PROMPT = """You are a senior C security expert. Your task is to extract concrete vulnerabilities that are explicitly present or clearly implied by the provided SECURITY ANALYSIS.

[SECURITY ANALYSIS]
{analysis}

STRICT OUTPUT CONTRACT:
- Output MUST be a single, valid JSON array of strings (UTF-8, no trailing comma).
- Do NOT include any extra text, labels, commentary, markdown, or code fences.
- If no concrete vulnerabilities can be extracted from the analysis, output [].
"""

    PATCH_PROMPT_TEMPLATE = """You are an expert C programmer and security specialist. Generate ONE patched, secure variant of the provided source code strictly based on the SECURITY ANALYSIS.

STRICT WORKFLOW (DO NOT OUTPUT THIS LIST):
1) Read SECURITY ANALYSIS and privately enumerate the concrete vulnerabilities that it explicitly states or clearly implies.
2) For THIS single variant, you MUST RETAIN EXACTLY the following vulnerability and FIX all other vulnerabilities supported by the SECURITY ANALYSIS:
   - VULNERABILITY TO RETAIN: {retained_vuln}
3) If any change would also fix the retained vulnerability, do NOT apply that change; instead, choose an alternative repair that still remediates the other issues while keeping the retained vulnerability observable.
4) Do NOT introduce or fix any issue that is not present or implied in the SECURITY ANALYSIS.

OUTPUT FORMAT:
- Output ONLY one complete C function wrapped in a single ```c ... ``` block. No extra text before or after.

[VULNERABLE CODE]
{code}

[SECURITY ANALYSIS]
{analysis}

[INSTRUCTION]
Generate ONE variant that retains ONLY the specified vulnerability and fixes all others supported by the SECURITY ANALYSIS. Ensure the retained vulnerability remains unfixed and observable. Do not introduce any fixes beyond the analysis scope."""

class LLMCaller:
    def __init__(self, api_key: str, model: str, base_url: str):
        self.base_url = base_url
        self.endpoint = f"{self.base_url}chat/completions"
        self.api_key = api_key
        self.model = model

    async def _async_create_completion(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.endpoint, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["message"]["content"].strip()
                else:
                    text = await response.text()
                    raise RuntimeError(f"LLM request failed, status={response.status}, body={text[:500]}")

    def create_completion(self, prompt: str) -> str:
        try:
            return asyncio.run(self._async_create_completion(prompt))
        except RuntimeError:
            import threading
            out = {"text": ""}
            err = {"e": None}
            def _worker():
                try:
                    out["text"] = asyncio.run(self._async_create_completion(prompt))
                except Exception as e:
                    err["e"] = e
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            t.join()
            if err["e"]:
                raise err["e"]
            return out["text"]

class DeepseekVariantPatcher:
    def __init__(self, model: str = "your_model", temperature: float = 0.0):
        self.llm = LLMCaller(model=model)
        self.model = model
        self.temperature = temperature

    def analyze_vulnerabilities(self, analysis_text: str) -> List[str]:
        prompt = Prompts.VULN_ANALYSIS_PROMPT.format(analysis=analysis_text)
        raw = self.llm.create_completion(prompt)
        return json.loads(raw) if raw else []

    def generate_variant(self, code: str, analysis_text: str, retained_vuln: str) -> Optional[str]:
        prompt = Prompts.PATCH_PROMPT_TEMPLATE.format(code=code, analysis=analysis_text, retained_vuln=retained_vuln)
        raw = self.llm.create_completion(prompt)
        return self.extract_code_block_from_model(raw)

    @staticmethod
    def extract_code_block_from_model(text: str) -> Optional[str]:
        if not text:
            return None
        m = re.search(r"```c\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def process_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        insecure_marker = "# Answer:\nInsecure"
        results: List[Dict[str, Any]] = []
        pbar = tqdm(total=len(entries), desc="Processing entries", dynamic_ncols=True)

        for idx, item in enumerate(entries):
            try:
                answer_text = item.get("answer", "")
                if not isinstance(answer_text, str) or insecure_marker not in answer_text:
                    pbar.update(1)
                    continue

                origin_code = item.get("origin_code", "")
                if not isinstance(origin_code, str) or not origin_code.strip():
                    logger.warning(f"[Index {idx}] Skip: missing/empty origin_code.")
                    pbar.update(1)
                    continue

                vulns = self.analyze_vulnerabilities(answer_text)
                if not vulns:
                    logger.info(f"[Index {idx}] No vulnerabilities parsed; skipping.")
                    pbar.update(1)
                    continue

                for v_desc in vulns:
                    variant_code = self.generate_variant(origin_code, answer_text, v_desc)
                    if variant_code:
                        result = dict(item)
                        result["index"] = idx 
                        result["patched_code"] = variant_code
                        results.append(result)

                pbar.update(1)  

            except Exception as e:
                logger.error(f"[Index {idx}] Error processing entry: {e}", exc_info=True)
                pbar.update(1) 
                continue

        pbar.close()  
        return results

def main():
    # Argument parsing for external parameters
    parser = argparse.ArgumentParser(description="Deepseek Variant Patcher")
    parser.add_argument("--base_url", type=str, required=True, help="Base URL for the API")
    parser.add_argument("--api_key", type=str, required=True, help="API key for authorization")
    parser.add_argument("--model", type=str, required=True, help="Model to use")
    parser.add_argument("--input_file", type=str, required=True, help="Input JSON file name")
    parser.add_argument("--output_file", type=str, required=True, help="Output JSON file name")

    args = parser.parse_args()

    input_file = args.input_file
    output_file = args.output_file

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            entries = json.load(f)
            if not isinstance(entries, list):
                raise ValueError("Input JSON must be a JSON array.")
    except Exception as e:
        logger.error(f"Failed to load input file: {e}")
        return

    patcher = DeepseekVariantPatcher(model=args.model)

    results = patcher.process_entries(entries)

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Results saved to: {output_file}")

if __name__ == "__main__":
    main()#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from tqdm import tqdm
import asyncio
import aiohttp
import argparse

logger = logging.getLogger("deepseek_variant_parallel_newio")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

class Prompts:
    VULN_ANALYSIS_PROMPT = """You are a senior C security expert. Your task is to extract concrete vulnerabilities that are explicitly present or clearly implied by the provided SECURITY ANALYSIS.

[SECURITY ANALYSIS]
{analysis}

STRICT OUTPUT CONTRACT:
- Output MUST be a single, valid JSON array of strings (UTF-8, no trailing comma).
- Do NOT include any extra text, labels, commentary, markdown, or code fences.
- If no concrete vulnerabilities can be extracted from the analysis, output [].
"""

    PATCH_PROMPT_TEMPLATE = """You are an expert C programmer and security specialist. Generate ONE patched, secure variant of the provided source code strictly based on the SECURITY ANALYSIS.

STRICT WORKFLOW (DO NOT OUTPUT THIS LIST):
1) Read SECURITY ANALYSIS and privately enumerate the concrete vulnerabilities that it explicitly states or clearly implies.
2) For THIS single variant, you MUST RETAIN EXACTLY the following vulnerability and FIX all other vulnerabilities supported by the SECURITY ANALYSIS:
   - VULNERABILITY TO RETAIN: {retained_vuln}
3) If any change would also fix the retained vulnerability, do NOT apply that change; instead, choose an alternative repair that still remediates the other issues while keeping the retained vulnerability observable.
4) Do NOT introduce or fix any issue that is not present or implied in the SECURITY ANALYSIS.

OUTPUT FORMAT:
- Output ONLY one complete C function wrapped in a single ```c ... ``` block. No extra text before or after.

[VULNERABLE CODE]
{code}

[SECURITY ANALYSIS]
{analysis}

[INSTRUCTION]
Generate ONE variant that retains ONLY the specified vulnerability and fixes all others supported by the SECURITY ANALYSIS. Ensure the retained vulnerability remains unfixed and observable. Do not introduce any fixes beyond the analysis scope."""

class LLMCaller:
    def __init__(self, api_key: str, model: str, base_url: str):
        self.base_url = base_url
        self.endpoint = f"{self.base_url}chat/completions"
        self.api_key = api_key
        self.model = model

    async def _async_create_completion(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.endpoint, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["message"]["content"].strip()
                else:
                    text = await response.text()
                    raise RuntimeError(f"LLM request failed, status={response.status}, body={text[:500]}")

    def create_completion(self, prompt: str) -> str:
        try:
            return asyncio.run(self._async_create_completion(prompt))
        except RuntimeError:
            import threading
            out = {"text": ""}
            err = {"e": None}
            def _worker():
                try:
                    out["text"] = asyncio.run(self._async_create_completion(prompt))
                except Exception as e:
                    err["e"] = e
            t = threading.Thread(target=_worker, daemon=True)
            t.start()
            t.join()
            if err["e"]:
                raise err["e"]
            return out["text"]

class DeepseekVariantPatcher:
    def __init__(self, model: str = "your_model", temperature: float = 0.0):
        self.llm = LLMCaller(model=model)
        self.model = model
        self.temperature = temperature

    def analyze_vulnerabilities(self, analysis_text: str) -> List[str]:
        prompt = Prompts.VULN_ANALYSIS_PROMPT.format(analysis=analysis_text)
        raw = self.llm.create_completion(prompt)
        return json.loads(raw) if raw else []

    def generate_variant(self, code: str, analysis_text: str, retained_vuln: str) -> Optional[str]:
        prompt = Prompts.PATCH_PROMPT_TEMPLATE.format(code=code, analysis=analysis_text, retained_vuln=retained_vuln)
        raw = self.llm.create_completion(prompt)
        return self.extract_code_block_from_model(raw)

    @staticmethod
    def extract_code_block_from_model(text: str) -> Optional[str]:
        if not text:
            return None
        m = re.search(r"```c\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def process_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        insecure_marker = "# Answer:\nInsecure"
        results: List[Dict[str, Any]] = []
        pbar = tqdm(total=len(entries), desc="Processing entries", dynamic_ncols=True)

        for idx, item in enumerate(entries):
            try:
                answer_text = item.get("answer", "")
                if not isinstance(answer_text, str) or insecure_marker not in answer_text:
                    pbar.update(1)
                    continue

                origin_code = item.get("origin_code", "")
                if not isinstance(origin_code, str) or not origin_code.strip():
                    logger.warning(f"[Index {idx}] Skip: missing/empty origin_code.")
                    pbar.update(1)
                    continue

                vulns = self.analyze_vulnerabilities(answer_text)
                if not vulns:
                    logger.info(f"[Index {idx}] No vulnerabilities parsed; skipping.")
                    pbar.update(1)
                    continue

                for v_desc in vulns:
                    variant_code = self.generate_variant(origin_code, answer_text, v_desc)
                    if variant_code:
                        result = dict(item)
                        result["index"] = idx 
                        result["patched_code"] = variant_code
                        results.append(result)

                pbar.update(1)  

            except Exception as e:
                logger.error(f"[Index {idx}] Error processing entry: {e}", exc_info=True)
                pbar.update(1) 
                continue

        pbar.close()  
        return results

def main():
    # Argument parsing for external parameters
    parser = argparse.ArgumentParser(description="Deepseek Variant Patcher")
    parser.add_argument("--base_url", type=str, required=True, help="Base URL for the API")
    parser.add_argument("--api_key", type=str, required=True, help="API key for authorization")
    parser.add_argument("--model", type=str, required=True, help="Model to use")
    parser.add_argument("--input_file", type=str, required=True, help="Input JSON file name")
    parser.add_argument("--output_file", type=str, required=True, help="Output JSON file name")

    args = parser.parse_args()

    input_file = args.input_file
    output_file = args.output_file

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            entries = json.load(f)
            if not isinstance(entries, list):
                raise ValueError("Input JSON must be a JSON array.")
    except Exception as e:
        logger.error(f"Failed to load input file: {e}")
        return

    patcher = DeepseekVariantPatcher(model=args.model)

    results = patcher.process_entries(entries)

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Results saved to: {output_file}")

if __name__ == "__main__":
    main()