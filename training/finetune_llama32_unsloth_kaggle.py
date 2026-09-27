"""
=============================================================================
KAGGLE T4 FINE-TUNING PIPELINE: Llama-3.2-3B-Instruct for Education & Tutoring
=============================================================================
Run this script inside a Kaggle Notebook with Accelerator set to:
  GPU T4 x 2 (or single GPU T4) - FREE (30 Hours/Week)

Workflow:
1. On your local machine, run: python training/generate_training_dataset.py
2. On Kaggle, create a new Dataset and upload: training/edu_finetune_dataset.jsonl
3. Create a new Kaggle Notebook, attach the dataset, paste this script, and run!
4. Download the generated 'llama3.2-3b-edu-Q4_K_M.gguf' (~2.2 GB)
5. Load into Ollama on your RTX 2050 PC with: ollama create learning-companion -f Modelfile
=============================================================================
"""

# STEP 1: Install Unsloth and optimized dependencies
# Run these in your Kaggle notebook first:
# !pip install --no-deps "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
# !pip install --no-deps "xformers<0.0.29" "trl<0.9.0" peft accelerate bitsandbytes datasets

import os
import json
import torch
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# STEP 2: Configuration
max_seq_length = 2048  # Safe context window for textbook sections without KV-cache overflow
dtype = None           # Auto-detect (Float16 on T4, Bfloat16 on Ampere+)
load_in_4bit = True    # 4-bit QLoRA consumes only ~3.8 GB VRAM during training

print("[1/5] Loading Base Model: unsloth/Llama-3.2-3B-Instruct...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Llama-3.2-3B-Instruct",
    max_seq_length=max_seq_length,
    dtype=dtype,
    load_in_4bit=load_in_4bit,
)

# Apply standard Llama-3 chat template
tokenizer = get_chat_template(
    tokenizer,
    chat_template="llama-3",
    mapping={"role": "role", "content": "content", "user": "user", "assistant": "assistant"}
)

# STEP 3: Setup LoRA Adapters
print("[2/5] Initializing LoRA Adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_alpha=16,
    lora_dropout=0.0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

# STEP 4: Auto-detect dataset anywhere in Kaggle
print("[3/5] Locating and formatting dataset...")
import glob
jsonl_candidates = glob.glob("/kaggle/input/**/*.jsonl", recursive=True) + ["edu_finetune_dataset.jsonl"]
data_file = None
for c in jsonl_candidates:
    if os.path.exists(c) and os.path.getsize(c) > 0:
        data_file = c
        break

if not data_file:
    raise FileNotFoundError(
        "Could not find edu_finetune_dataset.jsonl! "
        "Please click '+ Add Input' on the right panel and upload edu_finetune_dataset.jsonl."
    )

print(f"Reading training data from: {data_file}")
examples_raw = []
with open(data_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            examples_raw.append(json.loads(line))

print(f"Loaded {len(examples_raw)} multi-subject training examples.")


def apply_chat_template(batch):
    texts = []
    for messages in batch["messages"]:
        formatted = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        texts.append(formatted)
    return {"text": texts}


hf_dataset = Dataset.from_dict({
    "messages": [ex["messages"] for ex in examples_raw]
}).map(apply_chat_template, batched=True)

# STEP 5: Supervised Fine-Tuning (SFTTrainer - Version Immune)
print("[4/5] Starting fine-tuning...")
import inspect

training_args = TrainingArguments(
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    warmup_steps=10,
    max_steps=150,           # ~25-30 minutes on free Kaggle T4
    learning_rate=2e-4,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=15,
    optim="adamw_8bit",
    weight_decay=0.01,
    lr_scheduler_type="cosine",
    seed=3407,
    output_dir="outputs",
)

trainer_params = {
    "model": model,
    "train_dataset": hf_dataset,
    "dataset_text_field": "text",
    "max_seq_length": max_seq_length,
    "dataset_num_proc": 2,
    "packing": False,
    "args": training_args,
}

# Auto-detect whether this trl version uses 'processing_class' or 'tokenizer'
sig = inspect.signature(SFTTrainer.__init__)
if "processing_class" in sig.parameters:
    trainer_params["processing_class"] = tokenizer
else:
    trainer_params["tokenizer"] = tokenizer

trainer = SFTTrainer(**trainer_params)
trainer_stats = trainer.train()
print(f"Training completed successfully! Final loss: {trainer_stats.training_loss:.4f}")

# STEP 6: Export to 4-Bit GGUF for Ollama local deployment
print("[5/5] Exporting Model to 4-bit GGUF (llama3.2-3b-edu-Q4_K_M.gguf)...")
model.save_pretrained_gguf(
    "llama3.2-3b-edu",
    tokenizer,
    quantization_method="q4_k_m"
)

# Render direct clickable download link inside Kaggle notebook
from IPython.display import display, FileLink
print("\n" + "="*70)
print("EXPORT COMPLETE! Click the link below to download your model directly:")
print("="*70)
display(FileLink("llama3.2-3b-edu-Q4_K_M.gguf"))
print("\nOr find 'llama3.2-3b-edu-Q4_K_M.gguf' in the right sidebar under 'Output / /kaggle/working/'.")
print("Move it into your local Learning_Companion/training/ folder and run:")
print("  ollama create learning-companion -f training/Modelfile")

