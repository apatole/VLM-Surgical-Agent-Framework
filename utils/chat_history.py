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

class ChatHistory:
    def __init__(self):
        # Each entry in history: (user_message, agent_message) tuple
        self.history = []

    def add_user_message(self, user_msg):
        self.history.append((user_msg, None))

    def add_bot_message(self, bot_msg):
        if not self.history:
            # If there's no user message yet, just add a None for user.
            self.history.append((None, bot_msg))
        else:
            # Add bot msg to the last user-bot pair if bot is currently None
            last_user, last_bot = self.history[-1]
            if last_bot is None:
                self.history[-1] = (last_user, bot_msg)
            else:
                # If last entry is already complete, start a new one.
                self.history.append((None, bot_msg))

    def to_list(self):
        # return a copy of the conversation as a list of [user_msg, bot_msg]
        return [[u, b] for (u,b) in self.history]

    def reset(self):
        self.history = []
        
    def has_message(self, message):
        """Check if a message already exists in the chat history"""
        for user_msg, _ in self.history:
            if user_msg == message:
                return True
        return False

    def update_chat_history(self, is_done, agent_response, prompt_complete, asr_text):
        if prompt_complete:
            # user finished speaking, we consider their message done
            self.add_user_message(asr_text)
        if is_done and agent_response:
            # LLM finished responding
            self.add_bot_message(agent_response)
