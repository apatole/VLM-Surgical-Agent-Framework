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

from abc import ABC, abstractmethod
import json
import logging
import yaml
import time
import tiktoken
from threading import Lock
import base64
import tempfile
import os
import requests
from openai import OpenAI

class Agent(ABC):
    _llm_lock = Lock()
    
    def __init__(self, settings_path, response_handler, agent_key=None):
        self._logger = logging.getLogger(f"{__name__}.{type(self).__name__}")        
        self.load_settings(settings_path, agent_key=agent_key)
        self.response_handler = response_handler
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.client = OpenAI(api_key="EMPTY", base_url=self.llm_url)
        self._wait_for_server()

    def load_settings(self, settings_path, agent_key=None):
        with open(settings_path, 'r') as f:
            full_config = yaml.safe_load(f)
        if agent_key and agent_key in full_config:
            self.agent_settings = full_config[agent_key]
        else:
            self.agent_settings = full_config
        self.description = self.agent_settings.get('description', '')
        self.max_prompt_tokens = self.agent_settings.get('max_prompt_tokens', 3000)
        self.ctx_length = self.agent_settings.get('ctx_length', 2048)
        self.agent_prompt = self.agent_settings.get('agent_prompt', '').strip()
        self.user_prefix = self.agent_settings.get('user_prefix', '')
        self.bot_prefix = self.agent_settings.get('bot_prefix', '')
        self.bot_rule_prefix = self.agent_settings.get('bot_rule_prefix', '')
        self.end_token = self.agent_settings.get('end_token', '')
        self.grammar = self.agent_settings.get('grammar', None)
        self.model_name = self.agent_settings.get('model_name', 'llama3.2')
        self.publish_settings = self.agent_settings.get('publish', {})
        self.llm_url = self.agent_settings.get('llm_url', "http://localhost:8000/v1")
        self.tools = self.agent_settings.get('tools', {})
        self._logger.debug(f"Agent config loaded. llm_url={self.llm_url}, model_name={self.model_name}")

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
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=request_messages,
                    temperature=temperature,
                    max_tokens=self.ctx_length
                )
                response_text = completion.choices[0].message.content if completion.choices else ""
                if display_output and self.response_handler:
                    self.response_handler.add_response(response_text)
                    self.response_handler.end_response()
                return response_text
            except Exception as e:
                self._logger.error(f"vLLM chat request failed: {e}", exc_info=True)
                return ""

    def stream_image_response(self, prompt, image_b64, grammar=None, temperature=0.0, display_output=True, extra_body=None):
        self._logger.debug(f"stream_image_response with model={self.model_name}")
        if not image_b64:
            self._logger.warning("No image data provided for image response, will use placeholder")
            # Create a placeholder to avoid errors - use a simple colored rectangle
            image_b64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/4QBoRXhpZgAATU0AKgAAAAgABAEaAAUAAAABAAAAPgEbAAUAAAABAAAARgEoAAMAAAABAAIAAAExAAIAAAARAAAATgAAAAAAAABgAAAAAQAAAGAAAAABcGFpbnQubmV0IDQuMy4xAP/bAEMAAgEBAgEBAgICAgICAgIDBQMDAwMDBgQEAwUHBgcHBwYHBwgJCwkICAoIBwcKDQoKCwwMDAwHCQ4PDQwOCwwMDP/bAEMBAgICAwMDBgMDBgwIBwgMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDP/AABEIAKAAoAMBIgACEQEDEQH/xAAfAAABBQEBAQEBAQAAAAAAAAAAAQIDBAUGBwgJCgv/xAC1EAACAQMDAgQDBQUEBAAAAX0BAgMABBEFEiExQQYTUWEHInEUMoGRoQgjQrHBFVLR8CQzYnKCCQoWFxgZGiUmJygpKjQ1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2d3h5eoOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4eLj5OXm5+jp6vHy8/T19vf4+fr/xAAfAQADAQEBAQEBAQEBAAAAAAAAAQIDBAUGBwgJCgv/xAC1EQACAQIEBAMEBwUEBAABAncAAQIDEQQFITEGEkFRB2FxEyIygQgUQpGhscEJIzNS8BVictEKFiQ04SXxFxgZGiYnKCkqNTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqCg4SFhoeIiYqSk5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2dri4+Tl5ufo6ery8/T19vf4+fr/2gAMAwEAAhEDEQA/APsugDFFI33TQBynj34oeGfhZpJ1DxLrVnpEGcIZ33SSt/djQZZz7KCa+dPFv/BUXw/aXzw+GvCuo6nCp+W41CdLRW9wgV2/MV8deM/iFqnxH8RzapqtxJLNIx2RFz5VuvZEH8I/U9TWct3JHkzuCDwO9fP4jM6snaCsvxPSwmT0opynrL8D9MvB3/BRzwLrl0kOqWesaBIx2+bNGtxCPdmjJIHuyivoTwj4y0jxzodvqeh6np+r6dcruilsp1mRvwIOM+o5r8cbcmSPemQR0I7V6Z8Cf2ivEXwI1KP7HcNf6OzZuNLuHPlOP7yHqj+4/EGscPmk0+WsrryN8VlFOUfaYZ69ux+slHevBP2Zf2rtA+OGnraPt0rxJCv77TJG5cf342P3kP6dDXvYOa+lpVYVYc0HdHy9ajUoT5KiswooxRWhkFFFFABRRRQAUUUUAFFFFABRRSNQB4R+23+0P/wq3wn/AGLpFwE8R6tGQrKcm0t+jSZ7Mfu+x3elfnvdXzXUzs7tJI7FndjksT1JPc16t+1t8R/+Fh/F7UJYpPM0/Tc2NseqsoOX/wC+iT9MV5MYWbayru9Twa+RzDEOdXlW0T7jLcLGnRU3vLX/ACNDSLxlkiY8HIBxXbKQYt3evM9ImMVyu05AkGQO1eg2kqyWgYNkFcEGvPo3sex1RYh+6Kt2qSwxPDcQvDPEcPHIpVlPuDVJOgqyn3a6Is0T8jrPhd+054g+F86xw3b6hpQOJLC5cvHj0Q/eT8OPavsf4R/G3Q/i/pBm0ydoriMf6Tp8xAmgP16r/tDI9cV+fPXpW14L8aap8PdcTUNJupLaZcK6j7sqf3XX+IH0/GvawOaTo+7PVfmeDj8ro4lc8Pdfqj9N6O9eJfs6ftI2nxY09dO1IRWfiCBcy2oO1bhR1eL/ABHVfYjFe20pQjUipRd0fOzhKlNwmrNBRRRVEhRRRQAUUUUAFFFFABSNS0jUAfBH7Xl+138ZtbcMSsE6W6Z7KiKMfmTXAx/L1GR2rf8Ajhcfavipr0hJbOpT8n6gH9Kw7cB0GelfF4mXNVk/M+5w0eWjBeSJtJISdXPTdg/hXoVmuLFVz0UDFeewYW5GeozXodrxaoMenSsakbMqLuSp92rKdqqLytWE+7WsNiZEvQ1HNGJo2RhlXBDD3FOpO1bkHzl8YvhC3gfVZLq0iZ9JuG+ZegibHDfTsa4Kvy19K/EPw5H4u8I3lm4XzWTzIGP8Ei9PzHH418431pJZ3EkUsbRyRsUZHGCpHYivncywrpT5lo/yPpcpxqq0+SW6/M9P+AXxlk+G+sLY3sz/ANj3bgSKx/1D9BIvoOzD8e9fYMMqzRK6MrIwBVlOQQe4NflvG+9ecfWvcv2efjc2nyp4f1aY+USBNM7H5PTyzn/x3t26dPQyvMOV+xqPR7HnZzl3MvaU1qtz6moooruj5MKKKKYBRRRQAUUUUAFMkOKfTHz09aAPgf4vvnxzrv8A1/zf+hGoLf7op/xSj87x9r7YH/ISuP8A0M1Dbfd6Cviq795+p+gUv4cPlEI+DnFel2g/0VcdMV5p0H0r0ywP+ir9KVSN0dEN0WR92rCfdqsv3asL91qIblS2HU1lwynFOb7ppn8Qq5bAedfEnQvP05L5FO+1O2TH9xv6H+deXEV7lq1qt5ZzRsM741XP1H+FeTTwNBM8bjDIxVh6EGvGx1PVTPbyyryp0x0W5oyOhrrvCXjO88H6mtzZylcndJGfuSL6MK5XO0UobeK5KdSVOSlHdHoVaUakHCa0Z+gvhjxFbeL9BtdRtXDRXCbsA/NG38St7gg1fr51/Zo8ctbahdaPI5EVwDNbgngyAYZR/vAZ+q19FV9hg8QsRRU1vs/U+BxmFeFrOD23Xo/60QUUUV2HnhRRRQAUUUUAIx4qGRuKlc8VWmbaKAPz7+KNv5HxC15W6f2lcnH/AAI1Ut4ztHsa0PirF5HxK19c5/4md0c/8DNV7eHCDnPFeHiIWqy9T6jDz5qUH5I5/wAX+K9G+H+mC/1/UIdJs3kEStOhYOxBOEB5JwCePSt1JfMiVl4VgCPoRmuV/aG/Zx1T9oyLS5LO+ttOfTBJ5QlyUlDkE5/2SFX8jUPwQ+GOo/DbSJoNSvobu4lm8xBbyB0hG0DDEZ5PJwfSs5UqapKop6vY2p16rqulCGiep3EY+QVYi+6tQx/dqeH7orKBrLcV+lQ4/eGpj0xUPaT61oTHc37U7I42P4GvLfEVj9j1e5jA+Xf5i/Ruf6/pXpVwP3beory34nXjJrCRA/LFGN/1Jrz8ZG8Uz1MvladjlzRSUteSe+YWs3r6dPFLGcPE6up9wa+x/Cmtrrnh+zu0IYTQqzY7NjDD8QRXxszV9T/s6XDXHw7t0Y5MVxKq/QkMf/Zq9TKKlpyj56/ceHn1G9KM/LT7/wDI9Dooor6I+SCiiigAooooAR+lVZs461afoKrS0AfFHxbg8n4m69HjGNSuP/Q2qK0h3RjnPFa3xsiMPxT8QKcf8hKc8f7xrNtYdyDnNeJiI3qS9T6fDyapQfkjI8U+F9P8X6PLp+qW6XNpLjchOCCDkEEdQR3FeT+Dv2VvDvhDXrfULe4v5ZrcllS4kDIpIxnA6mv8g/DrXVvGAc1ahXau76VnKPMrNnTGpytSirNGlEvyrU8belVo/u1NG21fpXPFGk9yZutRdpKkPWou0laGaHSH5GrzL4iDOvt/1zT+Qr1Cb/VmvMfiAP8AierX/rqv8q4sb/CZ6GX/AMRHLHrRRRXjnuhT4pGhmSRThkYMD6g0yg8ZoA/QW2l86BGCsm5QdrDBH0p9c98LP+RT01c58q3VePZR/Su74r7SD5oKXc/PKkeSbi9kFFFFWZhRRRQAj9KrTdKst0NVZ+KAPhX44Q+X8V/ED5GRfyn/AMerItIcxDJrX+O0Pk/FnX1x/wAvW7/x5TWTax7o+c/SvGrL3mfT4d3pw9EZGtaOmr2M1tKMpIuM+h7Eexryr4E6Tc2nivxZpM4zcaRqm2MnvGyqQfzx+Veu6lcizt5JW+6ik15J8Hf+Ri+IP/YSH/oC1pT0aZFZapm/F92rMPTiqsP3asw9a54mstyY9aj/ALxqU9ai/j/GuiJmSS/6s15t8Qh/xPkH/TMf1r0uX/VmvNviF/yH0/65j+ZrnxX8JnflztiDjaKWivFPeCiiigDvvhP8BNY+K/h28vbGW1hNtO0TRzs4YkAHPyjjg16H4P8A2R9c1+ULqrppduvLc75WH+6OB+J/CvY/2bf+RFn/AOvx/wD0FK9LruhgqMoKcndnm1MwrxqOEEku58rfFDwlJ4I8VahpczLI1tKVV1PDr1Vh7EEH8aqW8W6MZzmup/aAGfiTqHptt/8A0WtYtrHuQc14Ve6qSv3PpcP71GD8kWKKKKxOkRzwaq3HSpn+7VafpQB8I/HiLyvi5r65/wCXoN/48orJt4d0Y5zWt8fE2fGHXlx/y8Kf/HBWPZ/6ocZryqy96XqfTYZ3ow9EZmtWP2vTZ4s48xCM+nFeS/Bj/kY/F3/XdP8A0Fa9mnVZI2VhlWGCK8d+C/Hizxd/13T/ANBWtIdSK+zRpRfdqxFVeOrEVc8dzee5Meaj/j/GpT1qP+P8a6ImZJN/qzXnXxC/5D6/9cx/M16NP/qzXnXxD/5D6/8AXMfzNc+K/hs7st/io5qig9KK8Y90K0/Cnhu68X+ILPTbKPzLi6kCKP4V9WPoACSfQGsyvd/2QfBfkanrWouu5mAtIiewyGf9QB9DXRhqLrVVBdTixeIVChKo+mp9BeG9HTQ9BsbJBhLaFIh+AxVykoruj5bfUKKKKACiiigCh4hsF1bRry0f7txC8R/4EpH9a5S0i3RjnrXaVyOtWb6XrVzGejvkfQ8iuDFw+GXqephJ/HDyZcoooriO8R/u1Wm6VYfrVabrQB8J/tAxbPjJr64/5eVb/wAdrGs/9WOK2v2iotn7QGuKf+e6n/x0VkWf+rH0ryqy99n02G/gQ9Ec34jvBa2M7sQqhCeT2rgPgv8A8jJ4v/67p/6CtbHjm6zayQofmcYP07/zrG+DA2+JPF/H/LdP5LXQtKbMm71Ueh/xcVZiqr/HVmLpXNHc2nuTN1qL/lp+FS9qi/5adK6ImZJcH92a87+If/IfX/rmP5mvRLg/uzXnnxD/AORgX/rmP5muet/DZ3Zd/FR5/wBqKB0or5494+pfgx4Hbwb4HtYpU23l0PtNwP7rMOF/4CuB9c16BWF8L7F7HwJo8cgw/wBmjY+4K5B/MGt2vq6EHClGLPgMTVVWvOaduZ2CiiitTAKKKKACiiigAqnrWmLq+mzQsMFhkH0I6H8auUCplFSTTKjJxaaPMxH5Nw6HqpwfqKim+7W74s0j7Hdi4jH7mU8+zd/z/nWJL92vDqQcJOLPcpzU4qSK7nlaqzn5asP1NQSdagoPhL9o3/kv+uZ/5+F/9BFZNp9wfStf9o3/AJL/AK5/18L/AOgis/TX3RLXl1v4jPpMN/Ah6I5DXkN3eXEg6Fto+g4p3wnXb4h8W/8AXdP/AEBafqkbF7iQDIJ4HrSfCf8A5GPxb/13T/0Fa66atTMKnx3PRf46sxVWX71WY65o7ms9yY9aj/5adKl7VF/y06V0QM2SXH+rNeefEL/kYF/65j+ZrubrgV5z488MalqviAyWtpNOvlKCUQkZH1rCvb2bOzL2/bI4k9aKc6yRyMrqyMpwVYYIPuKbXz59IfVvgXS/7J8L6faY2+VbRo2P7+0Zb8ya2qZbReTbxx/3EVf0p9fa04qEVFdD4GtNzqSm+rCiiirMwooooAKKKKACkbmilZgoySAB3JoA5PxxqYmmSzjPEeGkx3Y9Pyr6AD6mqTMVt2PpTdRvGvLyWZvvSMW/xpJXzbt9K8KtU9pNs9ynBQgkU36mmk80/wDipj9KzKPgv9o3/kv+uf8AXZP/AEEVm6e2Y1rS/aM/5L/rn/XZP/QRWTpm5o1PpXl1f4jPpMN/Ah6I5m7JFxcZ4+bB+tO+E/8AyMfi3/run/oK0++hhNxMznIZyQKR9O+zaRf+WCuGiGT6ZroW1MxnrPU9FHWrMdVlOVqzFXPHc1nuSHtUX/LTpUv8NRf8tOldEDORYufu/jXnvjz/AJCQ/wCua/zNehXPQV518QP+QkP+ua/zNY4n+Gzry/8AjHPUlLRXz59If//Z"
        
        # Extract user message from prompt
        try:
            user_message = prompt.split("<|im_start|>user\n")[-1].split("<|im_end|>")[0].strip()
        except Exception:
            user_message = prompt  # Fallback if prompt doesn't have expected format
            
        file_path = None
        try:
            # Extract and decode base64 data
            try:
                raw_b64 = self._extract_raw_base64(image_b64)
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
                    file_path = tmp_file.name
                    tmp_file.write(base64.b64decode(raw_b64))
                self._logger.debug(f"Temp image file created: {file_path}")
            except Exception as img_error:
                self._logger.error(f"Failed to process image data: {img_error}", exc_info=True)
                raise ValueError(f"Invalid image data: {img_error}")
            
            # Create message structure with explicit instruction to look at the image
            messages = []
            if self.agent_prompt:
                messages.append({"role": "system", "content": self.agent_prompt})
            
            # Add "you can see the image attached to this message" to ensure model knows there's an image
            modified_message = user_message
            if "tool" in user_message.lower() or "instrument" in user_message.lower():
                # Only add this instruction for tool/instrument related questions
                if not "image" in user_message.lower():
                    modified_message = f"{user_message} (Please look at the surgery image attached to this message)"
            
            messages.append({
                "role": "user",
                "content": modified_message,
                "images": [file_path]
            })
            
            # Setup request parameters
            request_kwargs = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": self.ctx_length
            }
            if extra_body is not None:
                request_kwargs["extra_body"] = extra_body
                
            # Make the API request with timeout handling
            try:
                result = self.client.chat.completions.create(**request_kwargs)
                
                # Process the response
                if result and result.choices and len(result.choices) > 0:
                    raw_text = result.choices[0].message.content
                    if display_output and self.response_handler:
                        self.response_handler.add_response(raw_text)
                        self.response_handler.end_response()
                    return raw_text
                else:
                    self._logger.warning("Empty or invalid response from vLLM")
                    return ""
                    
            except requests.exceptions.Timeout:
                self._logger.error("vLLM request timed out")
                raise TimeoutError("Model request timed out")
            except Exception as api_error:
                self._logger.error(f"vLLM API request failed: {api_error}", exc_info=True)
                raise
                
        except Exception as e:
            self._logger.error(f"vLLM vision request failed: {e}", exc_info=True)
            raise
        finally:
            # Always clean up the temporary file
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self._logger.debug(f"Removed temporary file: {file_path}")
                except Exception as cleanup_error:
                    self._logger.warning(f"Failed to remove temporary file {file_path}: {cleanup_error}")

    def _extract_raw_base64(self, image_b64: str) -> str:
        prefix = "data:image/"
        if image_b64.startswith(prefix):
            parts = image_b64.split(',', 1)
            if len(parts) == 2:
                return parts[1]
            else:
                return image_b64
        else:
            return image_b64

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
