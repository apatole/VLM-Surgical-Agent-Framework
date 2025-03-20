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

# Trap SIGINT and kill all processes in the group
trap 'kill 0' EXIT INT

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting Surgical Agentic Framework Development Server ===${NC}"

# Start the development stack with live-reload
echo -e "${YELLOW}Starting development servers with live-reload...${NC}"
echo -e "${GREEN}✓ Tailwind CSS watcher${NC}"
echo -e "${GREEN}✓ Flask server with auto-reload${NC}"
echo -e "${GREEN}✓ Browser-sync for auto-refresh${NC}"

# Start the full dev stack
npm run dev:web

wait