# Faithfulness of Reasoning Traces in LLM-based Code Vulnerability Detection

Example code of our FSE paper (554). 

## 🔰Installation

```bash
pip install -r requirements.txt
```

## ✨Dataset Preparation

We selected nine datasets:  [Devig](https://huggingface.co/datasets/DetectVul/devign) , [BigVul](https://huggingface.co/datasets/bstee615/bigvul) , [D2A](https://huggingface.co/datasets/claudios/D2A) , [Draper](https://huggingface.co/datasets/claudios/Draper) , [DiverseVulns](https://huggingface.co/datasets/NathanNeves/diversevulns) , [REVEAL](https://huggingface.co/datasets/ivne20/reveal) , [SVEN](https://huggingface.co/datasets/bstee615/sven) , [VulDeePecker](https://huggingface.co/datasets/claudios/VulDeePecker) , [PrimeVul](https://huggingface.co/datasets/colin/PrimeVul) and ten models: [Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) , [Phi-4](https://huggingface.co/microsoft/phi-4) , [Mistral-7B-Instruct-v0.3](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3) , [CodeLlama-Ins-7b](https://huggingface.co/AndreyRzhaksinskiy/CDS-CodeLlama-Ins-7b-E2E-20241022_baseline) , [DeepSeek-R1-Distill-Llama-8B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-8B) , [DeepSeek-R1-Distill-Qwen-7B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B) , [DeepSeek-R1-Distill-Qwen-14B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-14B) , [NeuralExperiment-7b-MagicCoder-v5](https://huggingface.co/Kukedlc/NeuralExperiment-7b-MagicCoder-v5) , [MPT-7B-StoryWriter](https://huggingface.co/mosaicml/mpt-7b-storywriter) , [Qwen2.5-Coder-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct).

First, you need to download all the datasets and required models, configure their paths, and extract only the code segments marked as unsafe. The format of all objects in the dataset is:

```
```c{code}```
```

where `code` is the unsafe code in the dataset.

In our experiments, we split all the files, which is handled by the `divide.py` code in the folder, in the following format:

```
Example:
Original file: combined_full_patched_answer
Split file: combined_full_patched_answer_{i} // i ranges from 1 to 10
```

If you do not need to split the files, you need to modify the paths in the subsequent code to the paths of the entire files.

## 📝Experiments

### RQ2

Configure the dataset and the required model names, and modify the input and output paths in all code files in the Q1 folder.

```bash
1. python run.py --combined_dataset "/path/to/data.json" --base_output_dir "/path/to/output"
2. python get_code.py  --first_file "your_dataset_code.json" --results_root "your_out_put_dir" --combined_name "your_combined_name.json" --output_name "output.json"
3. python divide.py --root "your_base_dir" --input-name "your_data_all_answer.json" --prefix "your_data_all_answer_" --chunk-size 1000
4. python full_patched.py --api_key "your_api_key" --model_name "your_model" --base_url "https://your.api.url/" --input_file "your_input_file.json" --output_file "your_output_file.json"
5. python get_full_patched_data.py --base_dir "your_base_dir" --input_filename "your_input_filename.json" --output_filename "your_out_put_filename.json"
6. python run_full_patched.py --base_results_dir "/path/to/results" --input_basename "your_full_patched.json" --output_basename "your_output_basename.json" 
7. python cul_full_patched.py --base_dir "your_base_directory_path" --models "model1" "model2" "model3"...
```

### RQ3

Configure the dataset and the required model names, and modify the input and output paths in all code files in the Q2 folder.

```bash
1. python run.py --combined_dataset "/path/to/data.json" --base_output_dir "/path/to/output"
2. python get_code.py  --first_file "your_dataset_code.json" --results_root "your_out_put_dir" --combined_name "your_combined_name.json" --output_name "output.json"
3. python divide.py --root "your_base_dir" --input-name "your_data_all_answer.json" --prefix "your_data_all_answer_" --chunk-size 1000
4. python run_N_patched.py --base_results_dir /path/to/results --input_basename your_full_patched_file_name.json --output_basename your_output_filename.json
5. python N_patched.py --base_url "your_base_url" --api_key "your_api_key" --model "your_model" --input_file "your_first_file_name.json" --output_file "your_output_filename.json"
6. python get_N_patched_data.py --base_dir "/path/to/base_dir" --input_filename "your_N_patched_file_name.json" --output_filename "your_output_file_name.json"
7. python del_N_patched.py --base_dir "/path/to/base_dir" --models model1 model2 --code_name "your_N_patched_code_{i}.json" --answer_name "your_N_patched_answer_{i}.json"
8. python your_script_name.py --base_dir "/path/to/base_dir" --models "model1" "model2"....
```

### RQ4

Use LoRA to adjust the model. Thanks [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) for implementing an efficient tool to fine-tune LLMs.

For detailed usage instructions, please refer to  [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) . We will provide a training file example for `deepseek-qwen-7b`

Configure your dataset base directory and run the scripts in order:

```bash
python data/scripts/prune_qwen_files.py --dir "/path/to/dataset_root" --apply
python data/scripts/organize_qwen_files.py --dir "/path/to/dataset_root" --apply
python data/scripts/filter_secure_in_origin_code.py --dir "/path/to/dataset_root/full_patched" --apply
python data/scripts/stat_qwen_pairs.py --base "/path/to/dataset_root"
python data/scripts/build_n_patched_faithfulness.py --dir "/path/to/dataset_root/N_patched" --out "/path/to/dataset_root/result/N_patched.json" --pretty
python data/scripts/build_full_patched_faithfulness.py --dir "/path/to/dataset_root/full_patched" --out "/path/to/dataset_root/result/full_patched.json" --pretty
python data/scripts/merge_dataset_to_base.py --base "/path/to/dataset_root/result" --out "/path/to/dataset_root/data_base.json" --pretty
```

Switch to the script directory for the corresponding model and begin training:

```bash
./run_train.fish
```

Modify the file paths in RQ4 to correspond to the original reasoning, full_patch, and N_patched.

Terminal window 1:

```bash
vllm serve \
    <MODEL_PATH> \
    --tensor-parallel-size <TP_SIZE> \
    --enable-lora \
    --lora-modules <LORA_NAME>=<LORA_CHECKPOINT_PATH> \
    --max-lora-rank <LORA_RANK> \
    --served-model-name <MODEL_NAME>
```

Terminal window 2:

Repeat the script order of RQ2 and RQ3. In `run_lora.py`, adjust the corresponding model names and paths. Change the instances where `run.py` is executed in RQ2 and RQ3 to run `run_lora.py` instead.

```bash
python run_lora.py
```
