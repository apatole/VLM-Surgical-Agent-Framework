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

# utils/response_handler.py
import queue
import threading

class ResponseHandler:
    def __init__(self):
        self._response_queue = queue.Queue()
        self._muted = False
        self._lock = threading.Lock()

    def add_response(self, text):
        with self._lock:
            if not self._muted:
                self._response_queue.put((False, text))

    def end_response(self):
        with self._lock:
            if not self._muted:
                # True indicates the response is done
                self._response_queue.put((True, None))

    def reset_queue(self):
        with self._lock:
            while not self._response_queue.empty():
                self._response_queue.get()

    def is_empty(self):
        return self._response_queue.empty()

    def get_response(self):
        # returns (is_done, text)
        return self._response_queue.get()

    def mute(self):
        with self._lock:
            self._muted = True
            # Clear the queue
            while not self._response_queue.empty():
                self._response_queue.get()

    def unmute(self):
        with self._lock:
            self._muted = False

    def is_muted(self):
        with self._lock:
            return self._muted
