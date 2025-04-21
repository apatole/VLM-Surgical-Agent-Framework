# Host the Surgical Agent Framework in Docker Containers

This repository provides Docker containers for running the Surgical Agent Framework. The framework is split into three main components:

1. **vLLM Server**: Hosts the large language model for agent interactions
2. **Whisper Server**: Provides real-time speech-to-text capabilities
3. **UI Server**: Serves the web interface and coordinates communication

Each component runs in its own container for better isolation and scalability. The containers communicate over the host network for simplicity in development. Below are instructions for building and running each container.

**NOTE**: Do not use the ssh-tunnel to access the UI. Use the IP address of the host machine, e.g. http://10.19.183.143:8050

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
docker run -it --rm --net host --gpus all \
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
docker build \
  -t gitlab-master.nvidia.com:5005/holoscan/copilot-blueprint:whisper-dgpu \
  -f docker/Dockerfile.whisper .
```

- Run (model will be automatically downloaded)
```bash
docker run -it --rm --gpus all --net host \
  -v $HOME/nvidia/VLM-Surgical-Agent-Framework/models/whisper:/root/whisper \
  gitlab-master.nvidia.com:5005/holoscan/copilot-blueprint:whisper-dgpu \
  --model_cache_dir /root/whisper
```


## UI (hosting the web services and the agent framework)

- Build
```bash
docker build -t gitlab-master.nvidia.com:5005/holoscan/copilot-blueprint:ui -f docker/Dockerfile.ui .
```

- Run
```bash
docker run -it --rm --net host gitlab-master.nvidia.com:5005/holoscan/copilot-blueprint:ui
```



