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

from __future__ import annotations
from abc import ABC, abstractmethod

import json
import logging
import yaml
import time
import tiktoken
from threading import Lock
from typing import Any, List, Sequence
import base64
import tempfile
import os
import requests
from openai import OpenAI

class Agent(ABC):
    """
    Common functionality for every agent (chat, note‑taker, selector, …).
    A single, process‑wide lock guarantees that only one thread talks to the
    model at a time – that is important for vLLM’s streaming endpoint.
    """

    _llm_lock = Lock()
    
    def __init__(self, settings_path, response_handler, agent_key=None):
        self._logger = logging.getLogger(f"{__name__}.{type(self).__name__}")

        self.load_settings(settings_path, agent_key=agent_key)
        self.response_handler = response_handler

        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.client = OpenAI(api_key="EMPTY", base_url=self.llm_url)

        self._wait_for_server()

    def load_settings(self, settings_path, agent_key=None):
        """
        Load YAML config and populate the most frequently accessed attributes.
        """
        with open(settings_path, 'r') as f:
            full_config = yaml.safe_load(f)
        if agent_key and agent_key in full_config:
            self.agent_settings = full_config[agent_key]
        else:
            self.agent_settings = full_config

        # Optional overrides for model_name and llm_url via environment variables and a global YAML
        # Precedence: ENV > agent-specific config > global.yaml > default
        # ENV keys:
        #   model_name: VLLM_MODEL_NAME
        #   llm_url:    VLLM_URL
        # Global YAML path: $VLLM_GLOBAL_CONFIG, else <settings_dir>/global.yaml
        # Defaults: model_name='llama3.2', llm_url='http://localhost:8000/v1'
        global_cfg: dict = {}
        try:
            # Allow custom path via env, otherwise look next to the agent settings file
            env_global_cfg_path = os.environ.get("VLLM_GLOBAL_CONFIG")
            candidate_paths = []
            if env_global_cfg_path:
                candidate_paths.append(env_global_cfg_path)
            candidate_paths.append(os.path.join(os.path.dirname(settings_path), "global.yaml"))
            for cfg_path in candidate_paths:
                if cfg_path and os.path.isfile(cfg_path):
                    with open(cfg_path, 'r') as gf:
                        global_cfg = yaml.safe_load(gf) or {}
                    break
        except Exception as e:
            # Non-fatal: proceed without global config
            self._logger.debug(f"No global config loaded: {e}")

        env_model_name = os.environ.get("VLLM_MODEL_NAME")
        env_llm_url = os.environ.get("VLLM_URL")

        self.description = self.agent_settings.get('description', '')
        self.max_prompt_tokens = self.agent_settings.get('max_prompt_tokens', 3000)
        self.ctx_length = self.agent_settings.get('ctx_length', 2048)
        self.agent_prompt = self.agent_settings.get('agent_prompt', '').strip()
        self.user_prefix = self.agent_settings.get('user_prefix', '')
        self.bot_prefix = self.agent_settings.get('bot_prefix', '')
        self.bot_rule_prefix = self.agent_settings.get('bot_rule_prefix', '')
        self.end_token = self.agent_settings.get('end_token', '')
        self.grammar = self.agent_settings.get('grammar', None)

        self._logger.debug(
            f"Agent config ENV VARS. model_name={env_model_name}"
        )
        self.model_name = (
            env_model_name
            or self.agent_settings.get('model_name')
            or (global_cfg.get('model_name') if isinstance(global_cfg, dict) else None)
            or 'llama3.2'
        )
        self.publish_settings = self.agent_settings.get('publish', {})
        self.llm_url = (
            env_llm_url
            or self.agent_settings.get('llm_url')
            or (global_cfg.get('llm_url') if isinstance(global_cfg, dict) else None)
            or "http://localhost:8000/v1"
        )
        self.tools = self.agent_settings.get('tools', {})
        self._logger.debug(
            f"Agent config loaded. llm_url={self.llm_url}, model_name={self.model_name}"
        )

    def _wait_for_server(self, timeout=60):
        attempts = 0
        check_url = f"{self.llm_url}/models"
        while attempts < timeout:
            try:
                r = requests.get(check_url)
                if r.status_code == 200:
                    self._logger.info(f"✅ Successfully connected to vLLM server at {self.llm_url}")
                    return
            except Exception as e:
                if attempts % 5 == 0:  # Log less frequently to reduce clutter
                    self._logger.info(f"Waiting for vLLM server (attempt {attempts+1}/{timeout}): {e}")
                else:
                    self._logger.debug(f"Waiting for vLLM server (attempt {attempts+1}/{timeout}): {e}")
            time.sleep(1)
            attempts += 1
        
        # More helpful error message
        raise ConnectionError(
            f"⚠️ Unable to connect to vLLM server at {self.llm_url} after {timeout} seconds.\n"
            f"Please ensure the vLLM server is running at {self.llm_url}.\n"
            f"You can start it manually using: ./scripts/run_vllm_server.sh"
        )

    def stream_response(self, prompt, grammar=None, temperature=0.0, display_output=True):
        with Agent._llm_lock:
            user_message = prompt.split("<|im_start|>user\n")[-1].split("<|im_end|>")[0].strip()
            request_messages = []
            if self.agent_prompt:
                request_messages.append({"role": "system", "content": self.agent_prompt})
            request_messages.append({"role": "user", "content": user_message})
            self._logger.debug(
                f"Sending chat request to vLLM/OpenAI client. Model={self.model_name}, temperature={temperature}\nUser message:\n{user_message[:500]}"
            )
            try:
                request_kwargs = {
                    "model": self.model_name,
                    "messages": request_messages,
                    "temperature": temperature,
                    "max_tokens": self.ctx_length,
                }
                # If a JSON schema grammar is provided, use OpenAI-compatible response_format
                if grammar:
                    try:
                        schema_dict = json.loads(grammar) if isinstance(grammar, str) else grammar
                        request_kwargs["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "structured_output",
                                "schema": schema_dict,
                                "strict": True,
                            },
                        }
                        # Also include vLLM-specific guided_json for broader compatibility
                        request_kwargs["extra_body"] = {"guided_json": schema_dict}
                    except Exception as e:
                        self._logger.error(f"Failed to parse grammar for response_format: {e}")

                completion = self.client.chat.completions.create(**request_kwargs)
                response_text = completion.choices[0].message.content if completion.choices else ""
                if display_output and self.response_handler:
                    self.response_handler.add_response(response_text)
                    self.response_handler.end_response()
                return response_text
            except Exception as e:
                self._logger.error(f"vLLM chat request failed: {e}", exc_info=True)
                return ""

    def stream_image_response(
        self,
        prompt: str,
        image_b64: str,
        *,
        grammar: str | None = None,
        temperature: float = 0.0,
        display_output: bool = True,
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        """
        Send a multimodal (text + image) request. The format is a *list* in
        `content`, where every element has a “type” field (text, image_url,
        image_pil, …).  We therefore build:

        messages = [
            {"role": "system", "content": "..."},
            {"role": "user", "content": [
                {"type": "text", "text": "..."},
                {"type": "image_url",
                 "image_url": {"url": "data:image/jpeg;base64,<raw>"}}
            ]}
        ]
        """
        # 1 – extract the user text
        try:
            user_message = prompt.split("<|im_start|>user\n")[-1].split("<|im_end|>")[0].strip()
        except Exception:  # pragma: no cover
            user_message = prompt

        # 2 – prepare base64 (no tmp file needed any more)
        raw_b64 = self._extract_raw_base64(image_b64)

        # 3 – optionally reinforce the existence of the image
        modified_message = user_message
        if any(tok in user_message.lower() for tok in ("tool", "instrument")) and "image" not in user_message.lower():
            modified_message += " (Please look at the surgery image attached to this message.)"

        # 4 – assemble OpenAI‑compatible messages
        messages: list[dict[str, Any]] = []
        if self.agent_prompt:
            messages.append({"role": "system", "content": self.agent_prompt})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": modified_message},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{raw_b64}"},
                    },
                ],
            }
        )

        # 5 – send
        request_kwargs = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.ctx_length,
        }
        # Prefer modern response_format if grammar provided; fallback to extra_body passthrough
        if grammar:
            try:
                schema_dict = json.loads(grammar) if isinstance(grammar, str) else grammar
                request_kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": schema_dict,
                        "strict": True,
                    },
                }
                # Also include vLLM-specific guided_json for broader compatibility
                request_kwargs["extra_body"] = {"guided_json": schema_dict}
            except Exception as e:
                self._logger.error(f"Failed to parse grammar for response_format (image): {e}")
        elif extra_body is not None:
            # Backward compatibility: allow callers to pass extra vLLM-specific knobs
            request_kwargs["extra_body"] = extra_body

        self._logger.debug("Multimodal chat request (%s)…", self.model_name)
        with Agent._llm_lock:
            try:
                result = self.client.chat.completions.create(**request_kwargs)
                answer = result.choices[0].message.content if result.choices else ""
            except requests.exceptions.Timeout:
                self._logger.error("vLLM request timed out")
                raise TimeoutError("Model request timed out") from None
            except Exception:
                self._logger.exception("vLLM multimodal request failed")
                return ""

        if display_output and self.response_handler:
            self.response_handler.add_response(answer)
            self.response_handler.end_response()
        return answer

    @staticmethod
    def _extract_raw_base64(data_uri: str) -> str:
        """
        Accept either a complete “data:image/…;base64,AAAA” URI *or* the bare
        base‑64 blob and always return the raw part (AAAA…).
        """
        if data_uri.startswith("data:image/"):
            return data_uri.split(",", 1)[1]
        return data_uri

    def generate_prompt(self, text, chat_history):
        system_prompt = f"{self.bot_rule_prefix}\n{self.agent_prompt}\n{self.end_token}"
        user_prompt = f"\n{self.user_prefix}\n{text}\n{self.end_token}"
        token_usage = self.calculate_token_usage(system_prompt + user_prompt)
        chat_prompt = self.create_conversation_str(chat_history, token_usage)
        prompt = system_prompt + chat_prompt + user_prompt
        prompt += f"\n{self.bot_prefix}\n"
        return prompt

    def create_conversation_str(self, chat_history, token_usage, conversation_length=2):
        total_tokens = token_usage
        msg_hist = []
        for user_msg, bot_msg in chat_history[:-1][-conversation_length:][::-1]:
            if bot_msg:
                bot_msg_str = f"\n{self.bot_prefix}\n{bot_msg}\n{self.end_token}"
                bot_tokens = self.calculate_token_usage(bot_msg_str)
                if total_tokens + bot_tokens > self.max_prompt_tokens:
                    break
                total_tokens += bot_tokens
                msg_hist.append(bot_msg_str)
            if user_msg:
                user_msg_str = f"\n{self.user_prefix}\n{user_msg}\n{self.end_token}"
                user_tokens = self.calculate_token_usage(user_msg_str)
                if total_tokens + user_tokens > self.max_prompt_tokens:
                    break
                total_tokens += user_tokens
                msg_hist.append(user_msg_str)
        return "".join(msg_hist[::-1])

    def calculate_token_usage(self, text):
        return len(self.tokenizer.encode(text))

    @abstractmethod
    def process_request(self, input_data, chat_history):
        pass

    def append_json_to_file(self, json_object, file_path):
        try:
            if not os.path.isfile(file_path):
                with open(file_path, 'w') as f:
                    json.dump([json_object], f, indent=2)
            else:
                with open(file_path, 'r') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = []
                if not isinstance(data, list):
                    data = []
                data.append(json_object)
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            self._logger.error(f"append_json_to_file error: {e}", exc_info=True)
