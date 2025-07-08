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
# Configurable parameters (override with env vars or CLI args as you like)
################################################################################
MODEL_REPO=${MODEL_REPO:-"nvidia/Llama-3.2-11B-Vision-Surgical-CholecT50"}
MODEL_DIR=${MODEL_DIR:-"models/llm"}
PORT=${PORT:-8000}


################################################################################
# Resolve the on‑disk target path and download if necessary
################################################################################
MODEL_NAME="$(basename "${MODEL_REPO}")"
MODEL_PATH="${MODEL_DIR}/${MODEL_NAME}"

if [[ ! -d "${MODEL_PATH}" ]]; then
  echo "[run_vllm_server.sh] Model not found at ${MODEL_PATH}"
  echo "[run_vllm_server.sh] Downloading with huggingface‑cli …"
  huggingface-cli download "${MODEL_REPO}" \
      --local-dir "${MODEL_PATH}" \
      --local-dir-use-symlinks False
  echo "[run_vllm_server.sh] Download complete."
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
echo "Running ${MODEL_REPO} from: ${MODEL_PATH} ..."
python -m vllm.entrypoints.openai.api_server \
    --model "${MODEL_PATH}" \
    --port "${PORT}" \
    --max-model-len "8192" \
    --max-num-seqs "4" \
    --disable-mm-preprocessor-cache \
    --load-format "bitsandbytes" \
    --quantization "bitsandbytes" \
    --gpu-memory-utilization 0.3 \
    --enforce-eager