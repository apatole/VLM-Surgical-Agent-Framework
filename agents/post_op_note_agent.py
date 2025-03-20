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

import os
import json
import math
import logging
from .base_agent import Agent

class PostOpNoteAgent(Agent):
    def __init__(self, settings_path, response_handler=None, agent_key=None):
        super().__init__(settings_path, response_handler, agent_key=agent_key)
        self._logger = logging.getLogger(__name__)
        self.chunk_size = self.agent_settings.get("chunk_size", 20)

        self.schema_dict = {}
        if self.grammar:
            try:
                self.schema_dict = json.loads(self.grammar)
                self._logger.debug(f"Parsed grammar JSON schema: {self.schema_dict}")
            except json.JSONDecodeError as e:
                self._logger.error(f"Failed to parse 'grammar' as JSON: {e}")

    def process_request(self, input_data, chat_history, visual_info=None):
        return {
            "name": "PostOpNoteAgent",
            "response": "Invoke generate_post_op_note(procedure_folder) to produce and save the final note."
        }

    def generate_post_op_note(self, procedure_folder):
        try:
            self._logger.info(f"Starting post-op note generation for folder: {procedure_folder}")
            
            # Check if procedure folder exists
            if not os.path.isdir(procedure_folder):
                self._logger.error(f"Procedure folder does not exist: {procedure_folder}")
                return None
                
            annotation_json = os.path.join(procedure_folder, "annotation.json")
            notetaker_json = os.path.join(procedure_folder, "notetaker_notes.json")

            # Load annotations and notes
            self._logger.debug(f"Loading annotations from {annotation_json}")
            ann_list = self._load_json_array(annotation_json)
            if not ann_list:
                self._logger.warning("No annotation data found or unable to load annotations")
                
            self._logger.debug(f"Loading notes from {notetaker_json}")
            note_list = self._load_json_array(notetaker_json)
            if not note_list:
                self._logger.warning("No notetaker data found or unable to load notes")
                
            # Create default structure when data is missing
            if not ann_list and not note_list:
                self._logger.warning("Both annotation and notetaker data are missing or empty - creating default structure")
                return {
                    "procedure_information": {
                        "procedure_type": "Not specified",
                        "date": "Not specified",
                        "duration": "Not specified",
                        "surgeon": "Not specified"
                    },
                    "findings": ["No findings recorded"],
                    "procedure_timeline": [],
                    "complications": []
                }
                
            # Summarize annotations and notes
            ann_summary = self._chunk_summarize_annotation(ann_list)
            notes_summary = self._chunk_summarize_notetaker(note_list)

            user_msg = (
                f"Annotated summary:\n{ann_summary}\n\n"
                f"Notetaker summary:\n{notes_summary}\n\n"
                "Now produce a final post-op note in JSON format that conforms to the grammar."
            )

            final_prompt = (
                f"{self.agent_prompt}\n"
                f"<|im_start|>user\n"
                f"{user_msg}\n"
                f"<|im_end|>\n"
                f"{self.bot_prefix}\n"
            )
            self._logger.debug(f"Final post-op prompt: {final_prompt[:500]}...")

            raw_resp = self._ask_for_json(final_prompt)
            if not raw_resp:
                self._logger.error("Empty response received from vLLM")
                return None
                
            self._logger.debug(f"PostOp raw response: {raw_resp[:500]}")

            try:
                # Clean the response further if needed
                cleaned_resp = raw_resp.strip()
                # If response contains JSON starting markers, extract only the JSON part
                if "```json" in cleaned_resp:
                    cleaned_resp = cleaned_resp.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned_resp:
                    cleaned_resp = cleaned_resp.split("```")[1].split("```")[0].strip()
                
                final_json = json.loads(cleaned_resp)
                self._logger.debug(f"Successfully parsed JSON response")
            except json.JSONDecodeError as e:
                self._logger.warning(f"Failed to parse final post-op note JSON: {e}\nRaw={raw_resp[:500]}...")
                # Try multiple fallback approaches
                try:
                    # Approach 1: Look for patterns that look like JSON objects
                    import re
                    json_pattern = r'(\{[\s\S]*\})'
                    matches = re.findall(json_pattern, raw_resp)
                    if matches:
                        potential_json = matches[0]
                        self._logger.debug(f"Attempting to parse extracted JSON pattern: {potential_json[:500]}")
                        final_json = json.loads(potential_json)
                        self._logger.info("Successfully parsed JSON after regex extraction")
                        return final_json
                        
                    # Approach 2: Try to complete truncated JSON
                    if self._is_truncated_json(raw_resp):
                        self._logger.warning("Detected truncated JSON, attempting to fix...")
                        fixed_json = self._fix_truncated_json(raw_resp)
                        if fixed_json:
                            self._logger.info("Successfully reconstructed truncated JSON")
                            return fixed_json
                    
                    # Approach 3: Create a fallback basic structure
                    self._logger.warning("Creating fallback post-op note structure")
                    import datetime
                    fallback_json = {
                        "procedure_information": {
                            "procedure_type": "laparoscopic procedure",
                            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                            "duration": "Unknown",
                            "surgeon": "Not specified"
                        },
                        "findings": ["Procedure data incomplete or corrupted"],
                        "procedure_timeline": [],
                        "complications": []
                    }
                    return fallback_json
                except Exception as e2:
                    self._logger.error(f"All JSON parsing attempts failed: {e2}")
                    
                    # Last resort: Create minimal structure
                    import datetime
                    return {
                        "procedure_information": {
                            "procedure_type": "Unknown procedure",
                            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                        },
                        "findings": ["Error generating post-op note"]
                    }

            post_op_file = os.path.join(procedure_folder, "post_op_note.json")
            self._save_post_op_note(final_json, post_op_file)

            return final_json
            
        except Exception as e:
            self._logger.error(f"Unexpected error in generate_post_op_note: {e}", exc_info=True)
            return None

    def _ask_for_json(self, prompt_text: str):
        messages = []
        if self.agent_prompt:
            messages.append({"role": "system", "content": self.agent_prompt})

        user_content = prompt_text.split("<|im_start|>user\n")[-1].split("<|im_end|>")[0].strip()
        messages.append({"role": "user", "content": user_content})

        self._logger.debug("Calling vLLM for JSON response.")
        try:
            # First attempt with standard parameters
            result = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.3,
                max_tokens=self.ctx_length
            )
            content = result.choices[0].message.content
            # Strip any Python tag markers that might be in the response
            if content.startswith("<|python_tag|>"):
                content = content.replace("<|python_tag|>", "")
                
            # Check if we have a complete JSON response
            if self._is_truncated_json(content):
                self._logger.warning("Detected truncated JSON in first response, trying again with different parameters")
                # Try again with more structured approach
                structured_messages = [
                    {"role": "system", "content": f"{self.agent_prompt}\nIMPORTANT: Your response MUST be complete, valid JSON only. Do not truncate your response."},
                    {"role": "user", "content": f"Generate a post-operative note in JSON format. Keep it concise but complete.\n\n{user_content}"}
                ]
                
                # Second attempt with more explicit instructions and higher max_tokens
                result = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=structured_messages,
                    temperature=0.2,  # Lower temperature for more deterministic output
                    max_tokens=self.ctx_length * 2  # Double the tokens to ensure completion
                )
                content = result.choices[0].message.content
            
            return content
        except Exception as e:
            self._logger.error(f"Error getting response from vLLM server: {e}", exc_info=True)
            raise
            
    def _is_truncated_json(self, text):
        """Check if JSON appears to be truncated"""
        # Count opening and closing braces
        open_braces = text.count('{')
        close_braces = text.count('}')
        
        # Check if we have complete pairs
        if open_braces != close_braces:
            self._logger.warning(f"Potential truncated JSON: {open_braces} opening braces vs {close_braces} closing braces")
            return True
            
        # Check for typical truncation patterns
        if text.rstrip().endswith(',') or text.rstrip().endswith(':') or text.rstrip().endswith('"'):
            self._logger.warning(f"Potential truncated JSON: ends with delimiter")
            return True
            
        try:
            # Try to parse it
            json.loads(text.strip())
            return False
        except json.JSONDecodeError as e:
            # If there's a specific truncation error
            if "Expecting" in str(e) or "Unterminated" in str(e):
                self._logger.warning(f"JSON parse error suggests truncation: {e}")
                return True
            
            # Otherwise it might be invalid for other reasons
            return False
            
    def _fix_truncated_json(self, text):
        """Attempt to fix truncated JSON by completing missing structure"""
        import re
        import datetime
        
        try:
            # Clean the text
            text = text.strip()
            
            # Extract what looks like a JSON object 
            if '{' in text:
                # Get everything from the first opening brace
                potential_json = text[text.find('{'):]
                
                # Count braces to determine what's missing
                open_braces = potential_json.count('{')
                close_braces = potential_json.count('}')
                
                # Add missing closing braces
                if open_braces > close_braces:
                    missing_braces = open_braces - close_braces
                    potential_json += '}' * missing_braces
                
                # Fix common truncation issues
                # Remove trailing commas before closing braces
                potential_json = re.sub(r',\s*}', '}', potential_json)
                
                # Fix unterminated strings by checking if we have an odd number of quotes
                if potential_json.count('"') % 2 != 0:
                    # Add a closing quote to the last string that's missing one
                    last_quote_pos = potential_json.rfind('"')
                    if last_quote_pos > 0:
                        potential_json = potential_json[:last_quote_pos+1] + '"' + potential_json[last_quote_pos+1:]
                
                try:
                    # Try to parse the fixed JSON
                    fixed_json = json.loads(potential_json)
                    self._logger.info("Successfully fixed truncated JSON")
                    
                    # Ensure it has the required structure
                    base_structure = {
                        "procedure_information": {
                            "procedure_type": "laparoscopic procedure",
                            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                            "duration": "Unknown",
                            "surgeon": "Not specified"
                        },
                        "findings": [],
                        "procedure_timeline": [],
                        "complications": []
                    }
                    
                    # Add any missing sections
                    for key, default in base_structure.items():
                        if key not in fixed_json:
                            fixed_json[key] = default
                        elif fixed_json[key] is None:
                            fixed_json[key] = default
                            
                    # Ensure procedure_information has all required fields
                    if isinstance(fixed_json.get("procedure_information"), dict):
                        for field, default in base_structure["procedure_information"].items():
                            if field not in fixed_json["procedure_information"]:
                                fixed_json["procedure_information"][field] = default
                    
                    return fixed_json
                    
                except Exception as e:
                    self._logger.warning(f"Failed to fix and parse truncated JSON: {e}")
            
            # Couldn't fix it, return None to trigger fallback
            return None
            
        except Exception as e:
            self._logger.error(f"Error in _fix_truncated_json: {e}", exc_info=True)
            return None

    def _chunk_summarize_annotation(self, ann_list):
        if not ann_list:
            return "No annotation data found."
        
        lines = []
        
        # Track all unique tools, phases, and anatomy for comprehensive summary
        all_tools = set()
        all_phases = set()
        all_anatomy = set()
        
        for ann in ann_list:
            ts = ann.get("timestamp", "???")
            phase = ann.get("surgical_phase", "?")
            desc = ann.get("description", "?")
            
            # Extract and track tools, anatomy
            tools = ann.get("tools", [])
            anatomy = ann.get("anatomy", [])
            
            # Update our tracking sets
            if phase and phase != "?":
                all_phases.add(phase)
            if tools:
                all_tools.update(tools)
            if anatomy:
                all_anatomy.update(anatomy)
            
            # Create a more detailed line including tools and anatomy when available
            details = []
            if tools:
                details.append(f"Tools=[{', '.join(tools)}]")
            if anatomy:
                details.append(f"Anatomy=[{', '.join(anatomy)}]")
                
            if details:
                lines.append(f"[{ts}] Phase={phase}, {desc} {' '.join(details)}")
            else:
                lines.append(f"[{ts}] Phase={phase}, {desc}")
        
        # Add a summary line at the beginning to highlight all tools, phases, and anatomy
        summary_lines = []
        if all_phases:
            summary_lines.append(f"ALL PHASES: {', '.join(all_phases)}")
        if all_tools:
            summary_lines.append(f"ALL TOOLS: {', '.join(all_tools)}")
        if all_anatomy:
            summary_lines.append(f"ALL ANATOMY: {', '.join(all_anatomy)}")
            
        # Combine the summary header with the detailed lines
        if summary_lines:
            lines = summary_lines + ["---"] + lines
            
        return self._multi_step_chunk_summarize(lines, label="Annotation data")

    def _chunk_summarize_notetaker(self, note_list):
        if not note_list:
            return "No notetaker data found."
            
        # Log the actual count of notes for debugging
        self._logger.info(f"Processing {len(note_list)} notetaker notes")

        # Filter out empty or placeholder notes
        valid_notes = []
        for note in note_list:
            text = note.get("text", "").strip()
            title = note.get("title", "").strip()
            
            # Skip notes with empty or placeholder content
            if not text or text.lower() in ["take a note", "no text", "empty"]:
                self._logger.debug(f"Skipping empty/placeholder note: {note}")
                continue
                
            valid_notes.append(note)
            
        self._logger.info(f"Found {len(valid_notes)} valid notes after filtering")
        
        if not valid_notes:
            return "No substantive notetaker data found (0 valid notes)."

        lines = []
        # Add a note count header
        lines.append(f"TOTAL NOTES: {len(valid_notes)}")
        lines.append("---")
        
        for note in valid_notes:
            ts = note.get("timestamp", "???")
            txt = note.get("text", "(no text)")
            title = note.get("title", "")
            
            # Include the title if available
            if title:
                lines.append(f"[{ts}] TITLE: {title} | CONTENT: {txt}")
            else:
                lines.append(f"[{ts}] {txt}")

        return self._multi_step_chunk_summarize(lines, label="Notetaker data")

    def _multi_step_chunk_summarize(self, lines, label="Data"):
        # If no lines to summarize, return a default message
        if not lines:
            return f"No {label.lower()} available to summarize."
            
        if len(lines) <= self.chunk_size:
            block = "\n".join(lines)
            return self._ask_for_summary(block, label)
        else:
            try:
                chunk_summaries = []
                total = len(lines)
                n_chunks = math.ceil(total / self.chunk_size)
                idx = 0
                for i in range(n_chunks):
                    chunk = lines[idx:idx+self.chunk_size]
                    idx += self.chunk_size
                    chunk_text = "\n".join(chunk)
                    sub_summary = self._ask_for_summary(chunk_text, f"{label} chunk {i+1}/{n_chunks}")
                    if sub_summary: # Only add non-empty summaries
                        chunk_summaries.append(sub_summary)
                
                # If all chunk summaries failed, return a default message
                if not chunk_summaries:
                    return f"Unable to generate summary for {label.lower()}."
                    
                final_block = "\n\n".join(chunk_summaries)
                final_summary = self._ask_for_summary(final_block, f"{label} final summary")
                
                # If final summary is empty, use the first chunk summary
                if not final_summary and chunk_summaries:
                    final_summary = chunk_summaries[0]
                    
                return final_summary or f"Unable to generate final summary for {label.lower()}."
                
            except Exception as e:
                self._logger.error(f"Error in multi-step chunk summarization: {e}", exc_info=True)
                return f"Error summarizing {label.lower()}: {str(e)}"

    def _ask_for_summary(self, text_block, label="Data"):
        messages = []
        if self.agent_prompt:
            messages.append({"role": "system", "content": self.agent_prompt})

        user_prompt = (
            f"You are summarizing {label}.\n"
            f"Here is the data:\n\n{text_block}\n\n"
            "Please produce a concise summary.\n"
        )
        messages.append({"role": "user", "content": user_prompt})

        try:
            result = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.5,
                max_tokens=self.ctx_length
            )
            return result.choices[0].message.content.strip()
        except Exception as e:
            self._logger.error(f"Error summarizing {label} with vLLM: {e}")
            return ""

    def _load_json_array(self, filepath):
        if not os.path.isfile(filepath):
            self._logger.warning(f"File not found: {filepath}")
            return []
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                self._logger.debug(f"Loaded data from {filepath}: {data[:500] if len(str(data)) > 500 else data}")
                
                if not isinstance(data, list):
                    self._logger.warning(f"{filepath} is not a JSON list.")
                    return []
                
                # Check if we have valid content or just empty placeholders
                if not data:
                    self._logger.warning(f"{filepath} is an empty list.")
                    return []
                
                # Log the actual count of items
                self._logger.info(f"Loaded {len(data)} items from {filepath}")
                
                # For notetaker notes, we'll filter, not exclude completely
                if "notetaker_notes.json" in filepath:
                    # Check if we have at least one valid note
                    has_valid_note = any(
                        isinstance(item, dict) and 
                        item.get("text", "").strip() and 
                        item.get("text", "").lower().strip() not in ["", "take a note"]
                        for item in data
                    )
                    
                    if not has_valid_note:
                        self._logger.warning(f"{filepath} contains only empty or placeholder notes.")
                        return []
                    
                    return data
                
                # For annotation files, keep any non-empty list
                return data
        except json.JSONDecodeError as e:
            self._logger.error(f"Invalid JSON in {filepath}: {e}", exc_info=True)
            return []
        except Exception as e:
            self._logger.error(f"Error reading {filepath}: {e}", exc_info=True)
            return []

    def _save_post_op_note(self, note_json, filepath):
        try:
            with open(filepath, "w") as f:
                json.dump(note_json, f, indent=2)
            self._logger.info(f"Post-op note saved to: {filepath}")
        except Exception as e:
            self._logger.error(f"Error writing post-op note to {filepath}: {e}", exc_info=True)