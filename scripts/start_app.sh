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

LMM_LOG_FILE="${LMM_LOG_FILE:-./surgical_agentic_framework.log}"

# Trap SIGINT and kill all processes in the group
trap 'kill 0' EXIT INT

# Build CSS first if NPM is available
if command -v npm &> /dev/null
then
    echo "Building CSS with Tailwind..."
    npm run build:tailwind
fi

# 1) Start vLLM server first, which will serve models on port 8000 by default
echo "Starting vLLM server on port 8000..."
bash scripts/run_vllm_server.sh >> "${LMM_LOG_FILE}" 2>&1 &

# Function to check if vLLM server is up and responding
check_vllm_server() {
  if curl -s --max-time 5 -o /dev/null -w "%{http_code}" "http://localhost:8000/v1/models" | grep -q "200"; then
    return 0  # Success - server is up
  else
    return 1  # Failure - server is not up yet
  fi
}

# Wait for vLLM server to be ready with active polling
echo "Waiting for vLLM server to initialize..."
MAX_WAIT_TIME=180  # Maximum wait of 3 minutes
CHECK_INTERVAL=3   # Check every 3 seconds
ELAPSED_TIME=0

while [ $ELAPSED_TIME -lt $MAX_WAIT_TIME ]; do
  if check_vllm_server; then
    echo "✓ vLLM server is ready after ${ELAPSED_TIME} seconds!"
    break
  fi
  
  # Show progress indicator
  if [ $((ELAPSED_TIME % 10)) -eq 0 ]; then
    echo "Still waiting for vLLM server... ${ELAPSED_TIME}s elapsed"
  fi
  
  sleep $CHECK_INTERVAL
  ELAPSED_TIME=$((ELAPSED_TIME + CHECK_INTERVAL))
done

# Final status check
if ! check_vllm_server; then
  echo "Warning: vLLM server did not respond within ${MAX_WAIT_TIME} seconds."
  echo "Continuing startup anyway, but the application may not work correctly."
fi

# 2) Start the Whisper server (port 43001)
echo "Starting Whisper server on port 43001..."
python servers/whisper_online_server.py \
    --model large-v3-turbo \
    --port 43001 \
    --warmup-file jfk.flac &

# Function to check if Whisper server is listening on port 43001
check_whisper_server() {
  if command -v nc &> /dev/null; then
    if nc -z localhost 43001 2>/dev/null; then
      return 0  # Success - server is up
    else
      return 1  # Failure - server is not up yet
    fi
  else
    # Fallback if nc is not available
    if curl -s --max-time 2 -o /dev/null --connect-timeout 2 telnet://localhost:43001; then
      return 0
    else
      return 1
    fi
  fi
}

# Wait for Whisper server to initialize
echo "Waiting for Whisper server to initialize..."
MAX_WHISPER_WAIT=30  # 30 seconds maximum wait
WHISPER_CHECK_INTERVAL=1
WHISPER_ELAPSED=0

while [ $WHISPER_ELAPSED -lt $MAX_WHISPER_WAIT ]; do
  if check_whisper_server; then
    echo "✓ Whisper server is ready after ${WHISPER_ELAPSED} seconds!"
    break
  fi
  
  sleep $WHISPER_CHECK_INTERVAL
  WHISPER_ELAPSED=$((WHISPER_ELAPSED + WHISPER_CHECK_INTERVAL))
  
  # Show periodic progress updates
  if [ $((WHISPER_ELAPSED % 5)) -eq 0 ]; then
    echo "Still waiting for Whisper server... ${WHISPER_ELAPSED}s elapsed"
  fi
done

# Final check
if ! check_whisper_server; then
  echo "Warning: Whisper server did not respond within ${MAX_WHISPER_WAIT} seconds."
  echo "Continuing startup anyway, but speech recognition may not work correctly."
fi

# 3) Start our Python app
echo "Starting main application server..."
python servers/app.py &

wait
