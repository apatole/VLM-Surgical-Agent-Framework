# Finetuning the VLM for a New Surgical Procedure

This section explains how to adapt the base model [Qwen/Qwen2.5-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) to another procedure (e.g., appendectomy, colectomy, partial nephrectomy) using [Visual Instruction Tuning](https://arxiv.org/pdf/2304.08485) in the style of LLaVA. The output is a vLLM-servable checkpoint that plugs into this framework with only config file changes.

---

### 0. Choose a Base & Target

* **Base:** Start from [Qwen/Qwen2.5-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) or your existing surgical checkpoint.
* **Target:** Define a clear taxonomy for the new procedure:
    * **Phases/steps** (e.g., exposure → critical structure identification → division → closure)
    * **Key anatomy** (named structures, landmarks, pathological findings)
    * **Tools** (grasper, clip applier, energy device, stapler, etc.)
    * **Critical safety gates** (e.g., “critical view of safety” analogs, hemostasis checks)

---

### 1. Curate Data

1.  **Collect videos** of the target procedure (de-identified).
2.  **Extract frames** with timestamps using uniform or event-biased sampling. Example:
    ```bash
    ffmpeg -i input_procedure.mp4 -vf "fps=2,scale=1024:-1" frames/%08d.jpg
    ```
3.  **Create per-frame metadata** using manual labels and/or CV model outputs:
    ```json
    {
      "image": "frames/00012345.jpg",
      "video_id": "case_042",
      "timestamp_s": 615.2,
      "phase": "Calot_dissection",
      "anatomy": ["cystic_duct", "cystic_artery", "liver_edge"],
      "tools": ["grasper", "hook_cautery"],
      "events": ["bleeding_minor=false", "cv_safety_met=true"]
    }
    ```
    *If you lack frame-level labels, start with weak labels (clip-level), then iteratively refine high-value regions (e.g., before/after key events).*

---

### 2. Generate Visual-Instruction Data (Teacher-Student)

Following the [Visual Instruction Tuning](https://arxiv.org/pdf/2304.08485) method, use a strong text-only LLM (e.g., a GPT-class model) as a "teacher." Provide the symbolic scene description from step 1 (phase/anatomy/tools/safety flags) and ask the teacher to write instruction-following Q&A grounded in that scene.

Create **3 complementary sample types** per image:

1.  **Conversation:** Short Q&A about concrete visuals.
2.  **Detailed Description:** Rich, structured narration.
3.  **Reasoning & Safety:** Questions about next steps, pitfalls, rationale, and checklists.

**Teacher prompt template (per frame):**

```text
System: You are a surgical assistant that "sees" the following scene description.

Scene:
- Phase: {phase}
- Anatomy visible: {anatomy_list}
- Instruments: {tool_list}
- Safety state: {events_list}

Task:
1. Write 3–6 short Q&A pairs answerable from this scene (no speculation).
2. Write one detailed, structured description (using bullet points).
3. Write 1–2 reasoning Q&A pairs about safety checks, the next recommended step, or potential pitfalls.

Constraints:
- Use precise surgical language.
- Avoid claims that are not supported by the scene.
- Keep answers concise and unambiguous.
```

### 3. Pack Data in LLaVA-style Format

Store each training item as an image plus a multi-turn conversation.

Example:

```json
    {
    "image": "frames/00012345.jpg",
    "conversations": [
        {"from": "human", "value": "<image>\nWhat phase is shown?"},
        {"from": "assistant", "value": "Dissection of Calot's triangle."},
        {"from": "human", "value": "Which instruments are active?"},
        {"from": "assistant", "value": "A grasper and a hook cautery."},
        {"from": "human", "value": "State the next safe step."},
        {"from": "assistant", "value": "Continue blunt dissection until the cystic duct and artery are clearly separated and the safety criteria are met before clipping."}
    ],
    "meta": {
        "video_id": "case_042",
        "timestamp_s": 615.2,
        "phase": "Calot_dissection",
        "anatomy": ["cystic_duct","cystic_artery","liver_edge"],
        "tools": ["grasper","hook_cautery"]
    }
    }
```
It is recommended to have at least 20k image / frame pairs for a procedure for basic understanding, and preferable to have over 50k. 

### 4. Train (LoRA / QLoRA)

Use your preferred HF Transformers + PEFT training stack.

See here for instance, for Qwen2.5 VLM finetuning recipes: https://github.com/2U1/Qwen2-VL-Finetune.

A common recipe for VLM finetuning:

* Strategy: Freeze the vision tower & connector; apply LoRA to the LLM (and cross-modal blocks if available).

* Precision: bf16; gradient checkpointing: on; flash-attention: on (if supported).

* Resolution: 768–1024px (shortest side).

* Context Length: 4k tokens (or longer if you include long rationales).

* Batching: Use a micro-batch of 1–2 images; use gradient accumulation for an effective batch size of 16–64.

* Learning Rate (LR): 2e-5 for LLM LoRA; 1e-4 for any small projector layers if unfrozen.

* LoRA: rank 16–32, alpha 16–64, dropout 0.05.

* Epochs: 1–3 over your instruction dataset (use early stopping on a validation set).

* Loss: Calculate next-token loss only on the assistant outputs (mask user turns).

### 5. Sanity-Check & Validate

Run a quick qualitative sanity suite on held-out frames:

* Perception: “Which phase?”, “Which tools?”, “Name visible structures.”

* Safety: “Have safety criteria been met?”, “Are there any red flags?”

* Planning: “What is the next step?”, “If bleeding occurs now, list immediate actions.”

Look for:

* Precise, non-speculative answers grounded in the frame.

* Low hallucination (e.g., no unseen tools or anatomy).

* Stable outputs across adjacent frames (temporal coherence).

### 6. Export & Serve with vLLM

#### 1. If you trained with LoRA, merge the adapters into the base model, then save the result with `save_pretrained`.

#### 2. Place the merged model at:

```bash
models/llm/<Your-Procedure-Model>/
```

#### 3. Update the global agent config `configs/global.yaml` (single source of truth):
```yaml
# Relative path inside this repo to your exported model
model_name: "models/llm/<Your-Procedure-Model>"

# Optional: set this if you want the vLLM script to auto‑download
# the model when the folder is missing
# model_repo: "<org-or-user>/<Your-Procedure-Model>"
```

The vLLM server script (`scripts/run_vllm_server.sh`) reads `configs/global.yaml` automatically. You no longer need to edit the script to change models. You can still override at runtime with `VLLM_MODEL_NAME` (and `MODEL_REPO` for auto‑download).

Also update the logic for the individual agent `.yaml` files to suit your procedure workflow.

#### 4. Restart the stack (`npm start` or `./scripts/start_app.sh`).

vLLM will now serve your finetuned model and the agents will follow your designed workflow. 
