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

# Colors for better output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

LMM_LOG_FILE="${LMM_LOG_FILE:-./surgical_agentic_framework.log}"

# Trap SIGINT and kill all processes in the group
trap 'echo -e "\n${RED}Shutting down all services...${NC}"; kill 0' EXIT INT

echo -e "${BLUE}${BOLD}=== Starting Surgical Agentic Framework - DEVELOPMENT MODE ===${NC}"

# Build CSS first with Tailwind
echo -e "${YELLOW}Building CSS with Tailwind...${NC}"
npm run build:tailwind

# 1) Start vLLM server first, which will serve models on port 8000 by default
echo -e "${YELLOW}Starting vLLM server on port 8000...${NC}"
bash scripts/run_vllm_server.sh >> "${LMM_LOG_FILE}" 2>&1 &
VLLM_PID=$!
echo -e "${GREEN}✓ vLLM server started (PID: $VLLM_PID)${NC}"

# Wait for vLLM server to initialize with active checking
echo -e "${YELLOW}Waiting for vLLM server to initialize...${NC}"
VLLM_CHECK_URL="http://localhost:8000/v1/models"
MAX_WAIT=120  # Maximum wait time in seconds (2 minutes)
WAIT_INTERVAL=2  # Check every 2 seconds
TOTAL_WAIT=0

# Function to check if vLLM server is up
check_vllm_server() {
  if curl -s --max-time 5 -o /dev/null -w "%{http_code}" "${VLLM_CHECK_URL}" | grep -q "200"; then
    return 0  # Success - server is up
  else
    return 1  # Failure - server is not up yet
  fi
}

# Active polling with progress indicator
while [ $TOTAL_WAIT -lt $MAX_WAIT ]; do
  if check_vllm_server; then
    echo -e "\n${GREEN}✓ vLLM server is ready after ${TOTAL_WAIT} seconds!${NC}"
    break
  fi
  
  # Show a spinner animation
  case $(($TOTAL_WAIT % 4)) in
    0) SPINNER="/" ;;
    1) SPINNER="-" ;;
    2) SPINNER="\\" ;;
    3) SPINNER="|" ;;
  esac
  
  echo -ne "${YELLOW}${SPINNER} Waiting for vLLM server... ${TOTAL_WAIT}s elapsed (max ${MAX_WAIT}s)${NC}\r"
  
  sleep $WAIT_INTERVAL
  TOTAL_WAIT=$((TOTAL_WAIT + WAIT_INTERVAL))
done

# Final check to see if server is actually responding
if check_vllm_server; then
  echo -e "${GREEN}✓ vLLM server is responding at ${VLLM_CHECK_URL}${NC}"
else
  echo -e "\n${RED}✗ vLLM server did not respond within ${MAX_WAIT} seconds.${NC}"
  echo -e "${YELLOW}Continuing startup anyway, but the application may not work correctly...${NC}"
fi

# 2) Start the Whisper server (port 43001)
echo -e "${YELLOW}Starting Whisper server on port 43001...${NC}"
python servers/whisper_online_server.py \
    --model large-v3-turbo \
    --port 43001 \
    --warmup-file jfk.flac &
WHISPER_PID=$!
echo -e "${GREEN}✓ Whisper server started (PID: $WHISPER_PID)${NC}"

# Wait for Whisper server to initialize with active checking
echo -e "${YELLOW}Waiting for Whisper server to initialize...${NC}"
MAX_WHISPER_WAIT=30  # Maximum wait time in seconds
WHISPER_INTERVAL=1  # Check every 1 second
WHISPER_WAIT=0

# Function to check if Whisper server is up
check_whisper_server() {
  if nc -z localhost 43001 2>/dev/null; then
    return 0  # Success - server is up
  else
    return 1  # Failure - server is not up yet
  fi
}

# Active polling with progress indicator
while [ $WHISPER_WAIT -lt $MAX_WHISPER_WAIT ]; do
  if check_whisper_server; then
    echo -e "\n${GREEN}✓ Whisper server is ready after ${WHISPER_WAIT} seconds!${NC}"
    break
  fi
  
  # Show a spinner animation
  case $(($WHISPER_WAIT % 4)) in
    0) SPINNER="/" ;;
    1) SPINNER="-" ;;
    2) SPINNER="\\" ;;
    3) SPINNER="|" ;;
  esac
  
  echo -ne "${YELLOW}${SPINNER} Waiting for Whisper server... ${WHISPER_WAIT}s elapsed (max ${MAX_WHISPER_WAIT}s)${NC}\r"
  
  sleep $WHISPER_INTERVAL
  WHISPER_WAIT=$((WHISPER_WAIT + WHISPER_INTERVAL))
done

# Final check to see if server is actually responding
if check_whisper_server; then
  echo -e "${GREEN}✓ Whisper server is responding on port 43001${NC}"
else
  echo -e "\n${RED}✗ Whisper server did not respond within ${MAX_WHISPER_WAIT} seconds.${NC}"
  echo -e "${YELLOW}Continuing startup anyway, but speech recognition may not work...${NC}"
fi

# 3) Start development services with auto-reload
echo -e "${YELLOW}Starting development services with auto-reload...${NC}"
echo -e "${GREEN}✓ Tailwind CSS watcher${NC}"
echo -e "${GREEN}✓ Flask server with auto-reload (listening on all interfaces - 0.0.0.0)${NC}"
echo -e "${GREEN}✓ Browser-sync for auto-refresh${NC}"

# Define a custom npm script to run Flask on all interfaces
export FLASK_HOST=0.0.0.0
export FLASK_PORT=8050

# Start the main application server (app.py) instead of just the web server
echo -e "${GREEN}✓ Starting main application server (app.py)${NC}"
python servers/app.py &
APP_PID=$!

# Wait for app server to initialize
sleep 5

# Start the development services (CSS watcher and browser-sync)
echo -e "${GREEN}✓ Starting development services (Tailwind + Browser-Sync)${NC}"
npm run watch:tailwind &
TAILWIND_PID=$!

npm run dev:sync &
SYNC_PID=$!

echo -e "${GREEN}✓ Development services started (APP: $APP_PID, Tailwind: $TAILWIND_PID, Sync: $SYNC_PID)${NC}"

# Get IP addresses to display
LOCAL_IP=$(hostname -I | awk '{print $1}')
TAILSCALE_IP=$(ip addr show tailscale0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)

echo -e "\n${BLUE}${BOLD}All services started in development mode!${NC}"
echo -e "${BLUE}Access URLs:${NC}"
echo -e "  ${BOLD}Local:${NC}            http://localhost:8050"
echo -e "  ${BOLD}Network:${NC}          http://${LOCAL_IP}:8050"
[ ! -z "$TAILSCALE_IP" ] && echo -e "  ${BOLD}Tailscale:${NC}        http://${TAILSCALE_IP}:8050"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}\n"

wait