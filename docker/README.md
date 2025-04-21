docker run -it --rm \
  --net host \
  --gpus all \
  -v /home/local-mingxinz/checkpoints/lora_applied_multinode_4e_v3-4bit:/vllm-workspace/models/llm/Llama-3.2-11B-lora-surgical-4bit \
  gitlab-master.nvidia.com:5005/holoscan/copilot-blueprint:vllm-openai-v0.8.3-dgpu-a6000 \
  --model models/llm/Llama-3.2-11B-lora-surgical-4bit \
  --enforce-eager \
  --max-model-len 4096 \
  --max-num-seqs 8 \
  --disable-mm-preprocessor-cache \
  --load-format bitsandbytes \
  --quantization bitsandbytes

mkdir -p /home/local-mingxinz/.cache/whisper

docker run -it --rm \
  --gpus all \
  --net host \
  -v /home/local-mingxinz/.cache/whisper:/models_cache \
  whisper-service \
  --model_cache_dir /models_cache

## UI

docker build -t ui:latest -f docker/Dockerfile.ui .
docker run -it --rm --net host ui:latest



