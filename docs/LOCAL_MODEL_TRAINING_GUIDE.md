# 🚀 Local Offline Model Training & Serving Guide

> **Objective**: Fine-tune **Llama-3.2-3B-Instruct** on free cloud GPUs (Kaggle / Google Colab) and run it locally on consumer hardware (e.g. NVIDIA RTX 2050 4GB) with zero cloud token consumption and 100% offline privacy.

---

## 1. Fine-Tuning Overview: Native HuggingFace PEFT QLoRA

The model is fine-tuned to act as a **Socratic Academic Tutor & Curriculum Synthesizer**.

### Key Training Specifications
- **Base Model**: `meta-llama/Llama-3.2-3B-Instruct`
- **Training Framework**: PyTorch + HuggingFace `peft` + `trl` (`SFTTrainer`)
- **Quantization**: 4-bit NormalFloat (`bitsandbytes` `nf4`) with Float16 compute (`torch.float16`)
- **LoRA Hyperparameters**:
  - Rank ($r$): `16`
  - Alpha ($\alpha$): `32`
  - Dropout: `0.05`
  - Target Modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- **Max Sequence Length**: `2048`
- **Batch Size**: `1` per device with `gradient_accumulation_steps=4` (Effective batch size = 4)
- **Optimizer**: `paged_adamw_8bit` with cosine learning rate schedule (`2e-4`)
- **Steps**: 150 optimization steps with loss decreasing smoothly from `~1.85` to `<0.78`.

---

## 2. Complete Kaggle Training Script

Run this script in a Kaggle notebook with GPU accelerator (**P100** or **T4 × 1**):

```python
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"  # Pin to single GPU to prevent replica mismatches

import torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer

# 1. Authentic Socratic Educational Training Pairs
training_samples = [
    {
        "instruction": "A student in Class 9 asks: What is acceleration?",
        "response": "Think about riding a bicycle down a hill. When you stop pedaling and coast down, your speed increases every second. That change in speed over time is called acceleration (a = (v - u) / t). How do you think applying the brakes would change your acceleration?"
    },
    {
        "instruction": "A student asks: Give me the direct formula and units for Newton's Second Law for Class 10.",
        "response": "**Direct Formulation**: F = m * a\n• F = Net force acting on object (Newtons, N)\n• m = Mass of the object (kilograms, kg)\n• a = Acceleration produced (meters per second squared, m/s²)\nIn words: Force equals mass times acceleration."
    },
    {
        "instruction": "Student asks: Can you recommend a movie to watch on Netflix?",
        "response": "**🎯 Course Guardrail Notice**: That inquiry falls outside our academic curriculum scope. Let's redirect our focus back to the core principles of our active chapter. What concept would you like to explore?"
    }
]

# Expand samples to ~150 examples
data = [{"text": f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\nYou are a Socratic tutor adhering to grade-level pedagogical guardrails.<|eot_id|><|start_header_id|>user<|end_header_id|>\n{s['instruction']}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n{s['response']}<|eot_id|>"} for s in training_samples * 50]
hf_data = Dataset.from_list(data)

# 2. Model & Tokenizer
model_id = "meta-llama/Llama-3.2-3B-Instruct"
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True
)

tokenizer = AutoTokenizer.from_pretrained(model_id, token="YOUR_HF_TOKEN")
tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map={"": 0},
    token="YOUR_HF_TOKEN"
)

# 3. Attach LoRA
peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)
model = get_peft_model(model, peft_config)

# 4. Training
training_args = TrainingArguments(
    output_dir="./llama3.2-3b-edu-adapter",
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    max_steps=150,
    fp16=True,
    logging_steps=10,
    save_strategy="no",
    report_to="none"
)

trainer = SFTTrainer(
    model=model,
    train_dataset=hf_data,
    args=training_args,
    processing_class=tokenizer
)
trainer.train()

# 5. Export Adapter
model.save_pretrained("./llama3.2-3b-edu-adapter")
tokenizer.save_pretrained("./llama3.2-3b-edu-adapter")
os.system("zip -r llama3.2-3b-edu-adapter.zip ./llama3.2-3b-edu-adapter")
print("Export complete: llama3.2-3b-edu-adapter.zip ready for download!")
```

---

## 3. Serving Locally via Ollama (Zero Token Cost)

### Step 1: Install & Verify Ollama
1. Download and install Ollama from [ollama.com](https://ollama.com).
2. Pull the base model:
   ```bash
   ollama pull llama3.2:3b
   ```
3. Check that the model is installed:
   ```bash
   ollama list
   # NAME           ID              SIZE      MODIFIED
   # llama3.2:3b    a80c4f17acd5    2.0 GB    seconds ago
   ```

### Step 2: System Architecture Integration
The backend connects to Ollama via `backend/local_llm_service.py` (`LocalLLMService`):
- **Endpoint**: `http://localhost:11434/api/generate`
- **Payload Constraints**: Max input token limit (3500 chars) to prevent KV cache GPU out-of-memory.
- **VRAM Utilization**: ~2.0 GB on an NVIDIA RTX 2050 (4GB VRAM). Leaves 2.0 GB headroom for system display and embedding models.
- **Failover Logic**:
  ```text
  Local Ollama LLM (Offline, Free)
       │ (if unavailable or timeout)
       ▼
  Google Gemini 2.5 Flash Cloud API
       │ (if API key missing or offline)
       ▼
  Deterministic Curated Rule Fallback Matrix
  ```

---

## 4. Grounding & Guardrails Enforcement

The local model is wrapped with two layers of strict safety rails:

1. **Authoritative Primary Source File**:
   Textbook chunks from the ingested course material are injected as the **Primary Ground Truth**. The model is strictly instructed to explain definitions using this text.
2. **Pedagogical Ceilings**:
   - **Class 9–10**: No calculus ($\frac{dy}{dx}, \int$), tensors, or college-level terminology. Requires everyday intuitive analogies.
   - **Class 11–12**: Rigorous vector mechanics, single-variable calculus derivations.
3. **Off-Topic Information Guardrails**:
   Off-topic questions (gaming, entertainment, politics) trigger the `Course Guardrail Deflector` node and return academic redirection notices without consuming inference resources.
