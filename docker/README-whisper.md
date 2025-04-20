# Whisper Docker Container

This Docker container provides a standalone Whisper ASR (Automatic Speech Recognition) service using faster-whisper. It exposes the service on port 43001 and can be used as part of the Surgical Agentic Framework or as a standalone speech recognition service.

## Features

- Uses faster-whisper instead of OpenAI Whisper for improved performance
- Runs on CUDA for GPU acceleration
- Exposes the service on port 43001
- Includes health checks
- Automatically downloads the Whisper model on first run

## Requirements

- Docker
- NVIDIA GPU with CUDA support
- nvidia-docker2 or nvidia-container-toolkit

## Building the Container

```bash
docker build -t whisper-service -f Dockerfile.whisper .
```

## Running the Container

### Using Docker Run

```bash
docker run --gpus all -p 43001:43001 whisper-service
```

### Using Docker Compose

A docker-compose.yml file is provided for easy deployment:

```bash
docker-compose -f docker-compose.whisper.yml up
```

## Configuration

You can customize the Whisper service by modifying the following environment variables:

- `WHISPER_MODEL`: The Whisper model to use (default: large-v3-turbo)
- `WHISPER_PORT`: The port to expose (default: 43001)
- `WHISPER_HOST`: The host to bind to (default: 0.0.0.0)
- `WHISPER_LOG_LEVEL`: The log level (default: INFO)

Example:

```bash
docker run --gpus all -p 43001:43001 \
  -e WHISPER_MODEL=medium \
  -e WHISPER_LOG_LEVEL=DEBUG \
  whisper-service
```

## Using with the Surgical Agentic Framework

This container is designed to work seamlessly with the Surgical Agentic Framework. Simply replace the Whisper service in the framework with this containerized version.

## Troubleshooting

- If the container fails to start, check that CUDA is properly installed and configured.
- If the service is not responding, check the logs using `docker logs <container_id>`.
- Ensure that port 43001 is not already in use on your host machine.

## License

This project is licensed under the same license as the Surgical Agentic Framework. 