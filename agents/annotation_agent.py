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

import threading
import time
import logging
import os
import json
import queue
from typing import List
from pydantic import BaseModel
from .base_agent import Agent

class SurgeryAnnotation(BaseModel):
    timestamp: str
    elapsed_time_seconds: float
    tools: List[str]
    anatomy: List[str]
    surgical_phase: str
    description: str

class AnnotationAgent(Agent):
    def __init__(self, settings_path, response_handler, frame_queue, agent_key=None, procedure_start_str=None):
        super().__init__(settings_path, response_handler, agent_key=agent_key)
        self._logger = logging.getLogger(__name__)
        self.frame_queue = frame_queue  
        self.time_step = self.agent_settings.get("time_step_seconds", 10)

        if procedure_start_str is None:
            procedure_start_str = time.strftime("%Y_%m_%d__%H_%M_%S", time.localtime())
        self.procedure_start_str = procedure_start_str
        self.procedure_start = time.time()


        base_output_dir = self.agent_settings.get("annotation_output_dir", "procedure_outputs")
        subfolder = os.path.join(base_output_dir, f"procedure_{self.procedure_start_str}")
        os.makedirs(subfolder, exist_ok=True)

        self.annotation_filepath = os.path.join(subfolder, "annotation.json")
        self._logger.info(f"AnnotationAgent writing annotations to: {self.annotation_filepath}")

        self.annotations = []
        self.stop_event = threading.Event()

        # Start the background loop in a separate thread.
        self.thread = threading.Thread(target=self._background_loop, daemon=True)
        self.thread.start()
        self._logger.info(f"AnnotationAgent background thread started (interval={self.time_step}s).")

    def _background_loop(self):
        # Flag to track if a valid video is loaded
        video_loaded = False
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while not self.stop_event.is_set():
            try:
                # Attempt to get image data from the frame queue.
                try:
                    frame_data = self.frame_queue.get_nowait()
                    
                    # If we get here, we have a frame, so video is loaded
                    video_loaded = True
                    consecutive_errors = 0  # Reset error counter on successful frame fetch
                except queue.Empty:
                    self._logger.debug("No image data available; skipping annotation generation.")
                    time.sleep(self.time_step)
                    continue
                except Exception as e:
                    self._logger.error(f"Error accessing frame queue: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        self._logger.critical(f"Too many consecutive errors ({consecutive_errors}). Pausing annotation processing for 30 seconds.")
                        time.sleep(30)  # Longer pause after too many errors
                        consecutive_errors = 0  # Reset after pause
                    time.sleep(self.time_step)
                    continue
                
                # Check frame data validity
                if not frame_data or not isinstance(frame_data, str) or len(frame_data) < 1000:
                    self._logger.warning("Invalid frame data received")
                    time.sleep(self.time_step)
                    continue
                    
                # Only proceed with annotation if we've confirmed video is loaded
                if video_loaded:
                    annotation = self._generate_annotation(frame_data)
                    if annotation:
                        self.annotations.append(annotation)
                        try:
                            self.append_json_to_file(annotation, self.annotation_filepath)
                            self._logger.debug(f"New annotation appended to file {self.annotation_filepath}")
                        except Exception as e:
                            self._logger.error(f"Failed to write annotation to file: {e}")
                            
                        # Notify that a new annotation was generated
                        if hasattr(self, 'on_annotation_callback') and self.on_annotation_callback:
                            try:
                                self.on_annotation_callback(annotation)
                            except Exception as callback_error:
                                self._logger.error(f"Error in annotation callback: {callback_error}")
            except Exception as e:
                self._logger.error(f"Error in annotation background loop: {e}", exc_info=True)
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    self._logger.critical(f"Too many consecutive errors in background loop ({consecutive_errors}). Pausing for 30 seconds.")
                    time.sleep(30)
                    consecutive_errors = 0
            
            # Sleep between annotation attempts
            time.sleep(self.time_step)

    def _generate_annotation(self, frame_data):
        messages = []
        if self.agent_prompt:
            messages.append({"role": "system", "content": self.agent_prompt})
        user_content = "Please produce an annotation of the surgical scene based on the provided image, following the required schema."
        messages.append({"role": "user", "content": user_content})
        
        # Create a fallback annotation in case of errors
        fallback_annotation = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "elapsed_time_seconds": time.time() - self.procedure_start,
            "tools": ["none"],
            "anatomy": ["none"],
            "surgical_phase": "preparation",  # Default to preparation phase
            "description": "Unable to analyze the current frame due to a processing error."
        }
        
        # First, check if the frame data is valid
        if not frame_data or len(frame_data) < 1000:  # Arbitrary minimum length for valid image data
            self._logger.warning("Invalid or empty frame data received")
            return None
            
        try:
            # Parse the grammar specification 
            try:
                guided_params = {"guided_json": json.loads(self.grammar)}
            except json.JSONDecodeError as e:
                self._logger.error(f"Invalid JSON grammar: {e}")
                return fallback_annotation
                
            # Try to get a response from the model with retries
            max_retries = 2
            retry_count = 0
            raw_json_str = None
            
            while retry_count <= max_retries and raw_json_str is None:
                try:
                    raw_json_str = self.stream_image_response(
                        prompt=self.generate_prompt(user_content, []),
                        image_b64=frame_data,
                        temperature=0.3,
                        display_output=False,  # Don't show output to user
                        extra_body=guided_params
                    )
                except Exception as e:
                    retry_count += 1
                    self._logger.warning(f"Annotation model error (attempt {retry_count}/{max_retries}): {e}")
                    if retry_count > max_retries:
                        self._logger.error(f"All annotation attempts failed: {e}")
                        return fallback_annotation
                    time.sleep(1)  # Wait before retry
            
            if not raw_json_str:
                self._logger.warning("Empty response from model")
                return fallback_annotation
                
            self._logger.debug(f"Raw annotation response: {raw_json_str}")

            # Try to parse the response as valid JSON
            try:
                parsed = SurgeryAnnotation.model_validate_json(raw_json_str)
            except Exception as e:
                self._logger.warning(f"Annotation parse error: {e}")
                # Try to extract valid JSON if the response contains malformed output
                try:
                    # Look for JSON-like content between curly braces
                    import re
                    json_match = re.search(r'\{.*\}', raw_json_str, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        parsed = SurgeryAnnotation.model_validate_json(json_str)
                    else:
                        return fallback_annotation
                except Exception:
                    self._logger.warning("Failed to extract valid JSON from response")
                    return fallback_annotation

            # Create the annotation dict with timestamp
            annotation_dict = parsed.dict()
            timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            annotation_dict["timestamp"] = timestamp_str
            annotation_dict["elapsed_time_seconds"] = time.time() - self.procedure_start

            return annotation_dict

        except Exception as e:
            self._logger.warning(f"Annotation generation error: {e}")
            return fallback_annotation

    def process_request(self, input_data, chat_history):
        return {
            "name": "AnnotationAgent",
            "response": "AnnotationAgent runs in the background and generates annotations only when image data is available."
        }

    def stop(self):
        self.stop_event.set()
        self._logger.info("Stopping AnnotationAgent background thread.")
        self.thread.join()
