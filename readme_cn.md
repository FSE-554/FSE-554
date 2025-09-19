# Faithfulness of Reasoning Traces in LLM-based Code Vulnerability Detection

## 🔰 安装

```bash
pip install -r requirements.txt
```

## ✨ 数据集准备

我们选择了九个数据集： [Devig](https://huggingface.co/datasets/DetectVul/devign)、 [BigVul](https://huggingface.co/datasets/bstee615/bigvul)、 [D2A](https://huggingface.co/datasets/claudios/D2A)、 [Draper](https://huggingface.co/datasets/claudios/Draper)、 [DiverseVulns](https://huggingface.co/datasets/NathanNeves/diversevulns)、 [REVEAL](https://huggingface.co/datasets/ivne20/reveal)、 [SVEN](https://huggingface.co/datasets/bstee615/sven)、 [VulDeePecker](https://huggingface.co/datasets/claudios/VulDeePecker)、 [PrimeVul](https://huggingface.co/datasets/colin/PrimeVul) 以及十个模型：[Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)、 [Phi-4](https://huggingface.co/microsoft/phi-4)、 [Mistral-7B-Instruct-v0.3](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3)、 [CodeLlama-Ins-7b](https://huggingface.co/AndreyRzhaksinskiy/CDS-CodeLlama-Ins-7b-E2E-20241022_baseline)、 [DeepSeek-R1-Distill-Llama-8B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-8B)、 [DeepSeek-R1-Distill-Qwen-7B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B)、 [DeepSeek-R1-Distill-Qwen-14B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-14B)、 [NeuralExperiment-7b-MagicCoder-v5](https://huggingface.co/Kukedlc/NeuralExperiment-7b-MagicCoder-v5)、 [MPT-7B-StoryWriter](https://huggingface.co/mosaicml/mpt-7b-storywriter)、 [Qwen2.5-Coder-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct)。

首先，您需要下载所有数据集和所需模型，配置它们的路径，并提取标记为不安全的代码段。数据集中所有对象的格式为：

```
```c{code}```
```

其中 `code` 是数据集中标记为不安全的代码。

在我们的实验中，我们将所有文件进行拆分，这由文件夹中的 `divide.py` 代码处理，格式如下：

```
示例：
原始文件：combined_full_patched_answer
拆分文件：combined_full_patched_answer_{i} // i 的范围为 1 到 10
```

如果您不需要拆分文件，则需要将后续代码中的路径修改为整个文件的路径。

## 📝 实验

### RQ2: full-patch

配置数据集和所需模型名称，并修改 Q1 文件夹中所有代码文件的输入和输出路径。

```
python run.py --combined_dataset "/path/to/data.json" --base_output_dir "/path/to/output"
python get_code.py --first_file "your_dataset_code.json" --results_root "your_out_put_dir" --combined_name "your_combined_name.json" --output_name "output.json"
python divide.py --root "your_base_dir" --input-name "your_data_all_answer.json" --prefix "your_data_all_answer_" --chunk-size 1000
python full_patched.py --api_key "your_api_key" --model_name "your_model" --base_url "https://your.api.url/" --input_file "your_input_file.json" --output_file "your_output_file.json"
python get_full_patched_data.py --base_dir "your_base_dir" --input_filename "your_input_filename.json" --output_filename "your_out_put_filename.json"
python run_full_patched.py --base_results_dir "/path/to/results" --input_basename "your_full_patched.json" --output_basename "your_output_basename.json"
python cul_full_patched.py --base_dir "your_base_directory_path" --models "model1" "model2" "model3"...
```

### RQ3: N-patch

配置数据集和所需模型名称，并修改 RQ3 文件夹中所有代码文件的输入和输出路径。

```bash
1. python run.py --combined_dataset "/path/to/data.json" --base_output_dir "/path/to/output"
2. python get_code.py --first_file "your_dataset_code.json" --results_root "your_out_put_dir" --combined_name "your_combined_name.json" --output_name "output.json"
3. python divide.py --root "your_base_dir" --input-name "your_data_all_answer.json" --prefix "your_data_all_answer_" --chunk-size 1000
4. python run_N_patched.py --base_results_dir /path/to/results --input_basename your_full_patched_file_name.json --output_basename your_output_filename.json
5. python N_patched.py --base_url "your_base_url" --api_key "your_api_key" --model "your_model" --input_file "your_first_file_name.json" --output_file "your_output_filename.json"
6. python get_N_patched_data.py --base_dir "/path/to/base_dir" --input_filename "your_N_patched_file_name.json" --output_filename "your_output_file_name.json"
7. python del_N_patched.py --base_dir "/path/to/base_dir" --models model1 model2 --code_name "your_N_patched_code_{i}.json" --answer_name "your_N_patched_answer_{i}.json"
8. python your_script_name.py --base_dir "/path/to/base_dir" --models "model1" "model2"....
```

### RQ4: LoRA

使用 LoRA 调整模型。感谢 [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory) 提供了一种有效的工具来微调 LLM。

有关详细的使用说明，请参考 [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)。我们将提供 `deepseek-qwen-7b` 的训练文件示例。

配置您的数据集基本目录并按顺序运行脚本：

```bash
python data/scripts/prune_qwen_files.py --dir "/path/to/dataset_root" --apply
python data/scripts/organize_qwen_files.py --dir "/path/to/dataset_root" --apply
python data/scripts/filter_secure_in_origin_code.py --dir "/path/to/dataset_root/full_patched" --apply
python data/scripts/stat_qwen_pairs.py --base "/path/to/dataset_root"
python data/scripts/build_n_patched_faithfulness.py --dir "/path/to/dataset_root/N_patched" --out "/path/to/dataset_root/result/N_patched.json" --pretty
python data/scripts/build_full_patched_faithfulness.py --dir "/path/to/dataset_root/full_patched" --out "/path/to/dataset_root/result/full_patched.json" --pretty
python data/scripts/merge_dataset_to_base.py --base "/path/to/dataset_root/result" --out "/path/to/dataset_root/data_base.json" --pretty
```

切换到相应模型的脚本目录并开始训练：

```bash
./run_train.fish
```

在 RQ4 中修改文件路径以对应于原始推理、full-patch和 N-patch。

终端窗口 1:

```bash
vllm serve \
    <MODEL_PATH> \
    --tensor-parallel-size <TP_SIZE> \
    --enable-lora \
    --lora-modules <LORA_NAME>=<LORA_CHECKPOINT_PATH> \
    --max-lora-rank <LORA_RANK> \
    --served-model-name <MODEL_NAME>
```

终端窗口 2:

重复 RQ2 和 RQ3 的脚本顺序。在 `run_lora.py` 中，调整相应的模型名称和路径。将 RQ2 和 RQ3 中执行 `run.py` 的实例更改为执行 `run_lora.py`。

```bash
python run_lora.py
```

