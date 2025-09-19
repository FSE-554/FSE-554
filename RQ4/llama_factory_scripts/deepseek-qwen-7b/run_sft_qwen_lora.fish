#!/usr/bin/env fish
# 激活环境并启动多卡 LoRA SFT 训练
conda activate llama_factory
set -x NCCL_P2P_DISABLE 0
set -x NCCL_IB_DISABLE 0
set -x CUDA_VISIBLE_DEVICES 0,1,2,3,4,5,6,7
set -x PYTORCH_CUDA_ALLOC_CONF max_split_size_mb:128,expandable_segments:True
set -x HF_DATASETS_OFFLINE 1
set -x TRANSFORMERS_NO_ADVISORY_WARNINGS 1

# 可选：加速 tokenizer
set -x TOKENIZERS_PARALLELISM false

cd /root/students/hebingyi/LLaMA-Factory

torchrun --nproc_per_node=8 --master_port=29501 \
  src/train.py /root/students/hebingyi/llama_factory_scripts/llama3-8b/train_lora_qwen.yaml
