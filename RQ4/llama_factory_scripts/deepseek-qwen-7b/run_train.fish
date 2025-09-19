#!/usr/bin/env fish
# 4-GPU ZeRO-3 LoRA SFT for DeepSeek-R1-Distill-Qwen-7B
conda activate llama_factory
set -x CUDA_VISIBLE_DEVICES 0,1,2,3
# 适当降低 allocator 碎片影响
set -x PYTORCH_CUDA_ALLOC_CONF max_split_size_mb:128,expandable_segments:True
set -x NCCL_P2P_DISABLE 0
set -x NCCL_IB_DISABLE 0
set -x TRANSFORMERS_NO_ADVISORY_WARNINGS 1
set -x TOKENIZERS_PARALLELISM false

cd /root/students/hebingyi/LLaMA-Factory

torchrun --nproc_per_node=4 --master_port=29521 \
  src/train.py /root/students/hebingyi/llama_factory_scripts/deepseek-qwen-7b/train_lora_qwen.yaml
