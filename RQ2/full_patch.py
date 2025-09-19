#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch code patching script (DeepSeek API version, adapted for new input file/fields)

Usage:
    python patch_parallel.py --api_key your_api_key --model_name your_model --base_url your_base_url --input_file your_input_file.json --output_file your_output_file.json
"""

import os
import json
import re
import time
import logging
import asyncio
import aiohttp
import argparse
from pathlib import Path
from tqdm import tqdm  
from tenacity import retry, stop_after_attempt, wait_random_exponential

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

class DeepSeekCodePatcher:
    def __init__(self, api_key, model_name, base_url):
        self.model_name = model_name
        self.api_key = api_key 
        self.base_url = base_url
        self.api_endpoint = f"{self.base_url}chat/completions"

        logger.info(f"Initializing DeepSeekCodePatcher with model: {self.model_name}")

        self.patch_prompt_template = """You are an expert C programmer and security specialist. Your task is to generate a patched, secure version of the provided source code based on the security analysis.

**Follow these rules strictly:**
1. Your output MUST be a complete, self-contained C function.
2. Do NOT add or invent new functions for context.
3. Focus on fixing the identified issues, such as adding null checks, replacing unsafe functions (e.g., `strcpy` with `strncpy`), validating inputs, and preventing resource leaks.
4. The patched code should undergo re-evaluation to verify that no new vulnerabilities have been introduced; if any new vulnerabilities are identified, an alternative patching approach must be adopted to ensure that the fix does not introduce additional security risks.
5. The output should ONLY be the patched C code, wrapped in ```c ... ``` markdown. Do not include any other explanations, greetings, or text.

---
**[VULNERABLE CODE]:**{code}  
[SECURITY ANALYSIS]:
{analysis}

[INSTRUCTION]:
Based on the analysis, provide the patched version of the code. Remember, output only the complete C function in a markdown block.
"""

    async def _async_call_llm(self, messages):
        """
        Use asynchronous aiohttp to call the DeepSeek API
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}", 
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "max_tokens": 2048,
            "temperature": 0.0,
            "messages": messages,
            "stream": False
        }

        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.api_endpoint, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                text = await resp.text()
                raise RuntimeError(f"LLM request failed: status={resp.status}, body={text[:500]}")

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3))
    async def _call_deepseek_api(self, messages):
        return await self._async_call_llm(messages)

    def _parse_patch_response(self, response_text: str) -> str:
        if not isinstance(response_text, str):
            return ""
        m = re.search(r"```c(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return response_text.strip()

    async def patch_code_from_file(self, input_file: str, output_file: str = None):
        if not os.path.exists(input_file):
            logger.error(f"Input file not found: {input_file}")
            return

        if output_file is None:
            logger.error("Output file name must be provided.")
            return

        try:
            with open(input_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    raise ValueError("Input JSON must be a list of objects.")
                logger.info(f"Loaded {len(data)} items from {input_file}")
        except Exception as e:
            logger.error(f"Error reading input JSON: {e}")
            return

        patched_results = []
        start_time = time.time()

        insecure_marker = "# Answer:\nInsecure"

        async def process_item(item):
            if not isinstance(item, dict):
                return None

            answer_text = item.get("answer", "")
            origin_code = item.get("origin_code", "")

            if not (isinstance(answer_text, str) and insecure_marker in answer_text):
                return None

            if not isinstance(origin_code, str) or not origin_code.strip():
                logger.warning("Skipping item due to missing/empty origin_code.")
                return None

            user_prompt = self.patch_prompt_template.format(code=origin_code, analysis=answer_text)
            messages = [{"role": "user", "content": user_prompt}]
            try:
                api_response = await self._call_deepseek_api(messages)
                raw_content = api_response["choices"][0]["message"]["content"]
                patched_code = self._parse_patch_response(raw_content)

                new_obj = dict(item)
                new_obj["patched_code"] = patched_code
                return new_obj
            except Exception as e:
                logger.error(f"Failed to patch one item: {e}")
                return {**item, "patched_code": f"// PATCHING FAILED: {e}"}

        tasks = [process_item(item) for item in tqdm(data, desc="Patching Insecure Code")]

        patched_results = await asyncio.gather(*tasks)

        patched_results = [result for result in patched_results if result]

        out_dir = os.path.dirname(output_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(patched_results, f, ensure_ascii=False, indent=2)

        total_time = time.time() - start_time
        logger.info("Code patching complete!")
        logger.info(f"Input items: {len(data)}, Patched items: {len(patched_results)}")
        logger.info(f"Results saved to: {output_file}")
        logger.info(f"Total time: {total_time:.2f} seconds")

async def main():
    parser = argparse.ArgumentParser(description="Batch code patching script using DeepSeek API")
    parser.add_argument("--api_key", type=str, required=True, help="Your API key for DeepSeek")
    parser.add_argument("--model_name", type=str, required=True, help="Model name to use with DeepSeek")
    parser.add_argument("--base_url", type=str, required=True, help="Base URL for the DeepSeek API")
    parser.add_argument("--input_file", type=str, required=True, help="Path to the input JSON file")
    parser.add_argument("--output_file", type=str, required=True, help="Path to the output JSON file")

    args = parser.parse_args()

    # Initialize the patcher with command line arguments
    patcher = DeepSeekCodePatcher(api_key=args.api_key, model_name=args.model_name, base_url=args.base_url)
    
    # Process the file
    await patcher.patch_code_from_file(args.input_file, args.output_file)

if __name__ == "__main__":
    asyncio.run(main())