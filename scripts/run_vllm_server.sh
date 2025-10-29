#!/bin/bash
# Copyright (c) MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

################################################################################
# Configuration
#
# Single source of truth for the model path is configs/global.yaml (model_name).
# You can override via env var VLLM_MODEL_NAME. If the on‑disk folder is
# missing, optionally set MODEL_REPO (or add model_repo in configs/global.yaml)
# so this script can auto‑download via huggingface‑cli.
################################################################################
set -euo pipefail

# Resolve repo root (script_dir/..)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Defaults
PORT=${PORT:-8000}

# Helper to extract a quoted YAML value by key from configs/global.yaml
GLOBAL_CFG="${REPO_ROOT}/configs/global.yaml"
read_yaml_key() {
  local key="$1"
  if [[ -f "${GLOBAL_CFG}" ]]; then
    grep -E "^${key}:" "${GLOBAL_CFG}" | sed "s/^${key}:[[:space:]]*//" | sed 's/^"//' | sed 's/"$//' 
  fi
}

# 1) Determine model path from ENV > configs/global.yaml > default
MODEL_NAME_REL="${VLLM_MODEL_NAME:-}"
if [[ -z "${MODEL_NAME_REL}" ]]; then
  MODEL_NAME_REL="$(read_yaml_key model_name || true)"
fi
if [[ -z "${MODEL_NAME_REL}" ]]; then
  MODEL_NAME_REL="models/llm/Qwen2.5-VL-7B-Surg-CholecT50"
fi

# Make absolute model path (allow absolute path in config)
if [[ "${MODEL_NAME_REL}" = /* ]]; then
  MODEL_PATH="${MODEL_NAME_REL}"
else
  MODEL_PATH="${REPO_ROOT}/${MODEL_NAME_REL}"
fi

# 2) Determine optional repo for auto‑download
MODEL_REPO_ENV="${MODEL_REPO:-}"
MODEL_REPO_CFG="$(read_yaml_key model_repo || true)"
MODEL_REPO_VAL="${MODEL_REPO_ENV:-${MODEL_REPO_CFG:-}}"

# 3) Served model name (for client-side model id)
SERVED_NAME_ENV="${SERVED_MODEL_NAME:-}"
SERVED_NAME_CFG="$(read_yaml_key served_model_name || true)"
SERVED_NAME_VAL="${SERVED_NAME_ENV:-${SERVED_NAME_CFG:-}}"


################################################################################
# Resolve the on‑disk target path and download if necessary
################################################################################
MODEL_NAME="$(basename "${MODEL_PATH}")"

# Kill on exit (graceful shutdown)
trap 'echo "[run_vllm_server.sh] Shutting down…"; pkill -P $$ || true' EXIT

if [[ ! -d "${MODEL_PATH}" ]]; then
  echo "[run_vllm_server.sh] Model not found at ${MODEL_PATH}"
  if [[ -n "${MODEL_REPO_VAL}" ]]; then
    echo "[run_vllm_server.sh] Downloading from ${MODEL_REPO_VAL} with huggingface‑cli …"
    huggingface-cli download "${MODEL_REPO_VAL}" \
        --local-dir "${MODEL_PATH}" \
        --resume-download \
        --local-dir-use-symlinks False
    echo "[run_vllm_server.sh] Download complete."
  else
    echo "[run_vllm_server.sh] No MODEL_REPO provided. Skipping auto‑download."
    echo "  Set env MODEL_REPO or add 'model_repo' to configs/global.yaml,"
    echo "  or manually download the model into: ${MODEL_PATH}"
    echo "  Example: huggingface-cli download nvidia/${MODEL_NAME} --local-dir \"${MODEL_PATH}\" --local-dir-use-symlinks False"
  fi
fi


################################################################################
# Export debugging env vars
################################################################################
export CUDA_LAUNCH_BLOCKING=1
export TORCH_USE_CUDA_DSA=1


################################################################################
# Launch vLLM in OpenAI‑compatible API mode
################################################################################
echo "[run_vllm_server.sh] Starting vLLM server on port ${PORT} …"
echo "Model path: ${MODEL_PATH}"
if [[ -n "${MODEL_REPO_VAL}" ]]; then
  echo "Model repo: ${MODEL_REPO_VAL}"
fi
if [[ -n "${SERVED_NAME_VAL}" ]]; then
  echo "Served model name: ${SERVED_NAME_VAL}"
fi
python -m vllm.entrypoints.openai.api_server \
    --model "${MODEL_PATH}" \
    --port "${PORT}" \
    --max-model-len "8192" \
    --max-num-seqs "1" \
    --mm-processor-cache-gb 0 \
    --load-format "bitsandbytes" \
    --quantization "bitsandbytes" \
    --gpu-memory-utilization 0.3 \
    --enforce-eager \
    --chat-template-content-format auto \
    $( [[ -n "${SERVED_NAME_VAL}" ]] && echo --served-model-name "${SERVED_NAME_VAL}" )
