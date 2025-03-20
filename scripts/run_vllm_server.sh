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

python -m vllm.entrypoints.openai.api_server \
    --model "models/llm/Llama-3.2-11B-lora-surgical-4bit/" \
    --port "8000" \
    --enforce-eager \
    --max-model-len "4096" \
    --max-num-seqs "8" \
    --disable-mm-preprocessor-cache \
    --load-format "bitsandbytes" \
    --quantization "bitsandbytes"
