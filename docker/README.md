## vllm
- Build
```bash
git clone -b v0.8.4-dgpu git@github.com:mingxin-zheng/vllm.git
cd vllm
DOCKER_BUILDKIT=1 docker build . \
  --file docker/Dockerfile \
  --target vllm-openai \
  --platform "linux/arm64" \
  -t gitlab-master.nvidia.com:5005/holoscan/copilot-blueprint:vllm-openai-v0.8.3-dgpu-a6000 \
  --build-arg RUN_WHEEL_CHECK=false
rm -rf vllm
```
- Download the model to $HOME/checkpoints/lora_applied_multinode_4e_v3-4bit
- Run
```bash
docker run -it --rm \
  --net host \
  --gpus all \
  -v $HOME/nvidia/VLM-Surgical-Agent-Framework/models/llm:/vllm-workspace/models \
  gitlab-master.nvidia.com:5005/holoscan/copilot-blueprint:vllm-openai-v0.8.3-dgpu-a6000 \
  --model models/llm/Llama-3.2-11B-lora-surgical-4bit \
  --enforce-eager \
  --max-model-len 4096 \
  --max-num-seqs 8 \
  --disable-mm-preprocessor-cache \
  --load-format bitsandbytes \
  --quantization bitsandbytes
```


## whisper
- Build
```bash
docker build -t whisper-service -f docker/Dockerfile.whisper .
```

- Run (model will be automatically downloaded to $HOME/.cache/whisper)
```bash
mkdir -p $HOME/.cache/whisper

docker run -it --rm \
  --gpus all \
  --net host \
  -v $HOME/.cache/whisper:/models_cache \
  whisper-service \
  --model_cache_dir /models_cache
```


## UI
- Build
```bash
docker build -t ui:latest -f docker/Dockerfile.ui .
```

- Run
```bash
docker run -it --rm --net host ui:latest
```



