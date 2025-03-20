# Surgical Agentic Framework Demo

The Surgical Agentic Framework Demo is a multimodal agentic AI framework tailored for surgical procedures. It supports:

* **Speech-to-Text**: Real-time audio is captured, transcribed by Whisper.
* **VLM/LLM-based Conversational Agents**: A *selector agent* decides which specialized agent to invoke:
    *   ChatAgent for general Q&A,
    *   NotetakerAgent to record specific notes,
    *   AnnotationAgent to automatically annotate progress in the background,
    *   PostOpNoteAgent to summarize all data into a final post-operative note.
* **(Optional) Text-to-Speech**: The system can speak back the AI's response if you enable TTS (ElevenLabs is implemented, but any local TTS could be implemented as well).
* **Computer Vision** or multimodal features are supported via a finetuned VLM (Vision Language Model), launched by vLLM.
* **Video Upload and Processing**: Support for uploading and analyzing surgical videos.
* **Post-Operation Note Generation**: Automatic generation of structured post-operative notes based on the procedure data.


## System Flow and Agent Overview

1. Microphone: The user clicks "Start Mic" in the web UI, or types a question.
2. Whisper ASR: Transcribes speech into text (via servers/whisper_online_server.py).
3. SelectorAgent: Receives text from the UI, corrects it (if needed), decides whether to direct it to:
    * ChatAgent (general Q&A about the procedure)
    * NotetakerAgent (records a note with timestamp + optional image frame)
    * In the background, AnnotationAgent is also generating structured "annotations" every 10 seconds.
4. NotetakerAgent: If chosen, logs the note in a JSON file.
5. AnnotationAgent: Runs automatically, storing procedure annotations in ```procedure_..._annotations.json```.
6. PostOpNoteAgent (optional final step): Summarizes the entire procedure, reading from both the annotation JSON and the notetaker JSON, producing a final structured post-op note.

## System Requirements

* Python 3.12 or higher
* Node.js 14.x or higher
* CUDA-compatible GPU (recommended) for model inference
* Microphone for voice input (optional)
* 16GB+ RAM recommended

## Installation 

1. Clone or Download this repository:

```
git clone https://github.com/monai/surgical_agentic_framework.git
cd surgical_agentic_framework
```

2. Setup vLLM (Optional)

vLLM is already configured in the project scripts. If you need to set up a custom vLLM server, see https://docs.vllm.ai/en/latest/getting_started/installation.html

3. Install Dependencies:

```
conda create -n surgical_agentic_framework python=3.12
conda activate surgical_agentic_framework
pip install -r requirements.txt
```

4. Install Node.js dependencies (for UI development):

```
npm install
```

5. Models Folder:

* Place your model files in ```models/llm/``` for LLMs and ```models/whisper/``` for Whisper models.
* This repository is configured to use a Llama-3.2-11B model with surgical fine-tuning.
* The model is served using vLLM for optimal performance.

* Folder structure is: 

```
models/
  ├── llm/
  │   └── Llama-3.2-11B-lora-surgical-4bit/  <-- LLM model files
  └── whisper/                               <-- Whisper models (downloaded at runtime)
```

6. Setup: 

* Edit ```scripts/start_app.sh``` if you need to change ports or model file names.

7. Create necessary directories:

```bash
mkdir -p annotations uploaded_videos
```

## Running the Surgical Agentic Framework Demo

### Production Mode

1. Run the full stack with all services:

```
npm start
```

Or using the script directly:

```
./scripts/start_app.sh
```

What it does:

* Builds the CSS with Tailwind
* Starts vLLM server with the model on port 8000
* Waits 45 seconds for the model to load
* Starts Whisper (servers/whisper_online_server.py) on port 43001 (for ASR)
* Waits 5 seconds
* Launches ```python servers/app.py``` (the main Flask + WebSockets application)
* Waits for all processes to complete

### Development Mode

For UI development with hot-reloading CSS changes:

```
npm run dev:web
```

This starts:
* The CSS watch process for automatic Tailwind compilation
* The web server only (no LLM or Whisper)

For full stack development:

```
npm run dev:full
```

This is the same as production mode but also watches for CSS changes.

You can also use the development script for faster startup during development:

```
./scripts/dev.sh
```

2. **Open** your browser at ```http://127.0.0.1:8050```. You should see the Surgical Agentic Framework Demo interface:
    * A video sample (```sample_video.mp4```)
    * Chat console
    * A "Start Mic" button to begin ASR.

3. Try speaking or Typing:
    * If you say "Take a note: The gallbladder is severely inflamed," the system routes you to NotetakerAgent.
    * If you say "What are the next steps after dissecting the cystic duct?" it routes you to ChatAgent.

4. Background Annotations:
    * Meanwhile, ```AnnotationAgent``` writes a file like: ```procedure_2025_01_18__10_25_03_annotations.json``` in the annotations folder very 10 seconds with structured timeline data.

## Uploading and Processing Videos

1. Click on the "Upload Video" button to add your own surgical videos
2. Browse the video library by clicking "Video Library" 
3. Select a video to analyze
4. Use the chat interface to ask questions about the video or create annotations

## Generating Post-Operation Notes

After accumulating annotations and notes during a procedure:

1. Click the "Generate Post-Op Note" button
2. The system will analyze all annotations and notes
3. A structured post-operation note will be generated with:
   * Procedure information
   * Key findings
   * Procedure timeline
   * Complications

## Troubleshooting

Common issues and solutions:

1. **WebSocket Connection Errors**:
   * Check firewall settings to ensure ports 49000 and 49001 are open
   * Ensure no other applications are using these ports
   * If you experience frequent timeouts, adjust the WebSocket configuration in `servers/web_server.py`

2. **Model Loading Errors**:
   * Verify model paths are correct in configuration files
   * Ensure you have sufficient GPU memory for the models
   * Check the log files for specific error messages

3. **Audio Transcription Issues**:
   * Verify your microphone is working correctly
   * Check that the Whisper server is running
   * Adjust microphone settings in your browser

## Text-to-Speech (Optional)

If you want to enable TTS with ElevenLabs (or implement your own local TTS server):
    * Follow the instructions in the index.html or your code snippet that calls a TTS route or API.
    * Provide your TTS API key if needed.

## File Structure

A brief overview:

```
surgical_agentic_framework/
├── agents/                 <-- Agent implementations
│   ├── annotation_agent.py
│   ├── base_agent.py
│   ├── chat_agent.py
│   ├── notetaker_agent.py
│   ├── post_op_note_agent.py
│   └── selector_agent.py
├── configs/                <-- Configuration files
│   ├── annotation_agent.yaml
│   ├── chat_agent.yaml
│   ├── notetaker_agent.yaml
│   ├── post_op_note_agent.yaml
│   └── selector.yaml
├── models/                 <-- Model files
│   ├── llm/                <-- LLM model files
│   │   └── Llama-3.2-11B-lora-surgical-4bit/
│   └── whisper/            <-- Whisper models (downloaded at runtime)
├── scripts/                <-- Shell scripts for starting services
│   ├── dev.sh              <-- Development script for quick startup
│   ├── run_vllm_server.sh
│   ├── start_app.sh        <-- Main script to launch everything
│   └── start_web_dev.sh    <-- Web UI development script
├── servers/                <-- Server implementations
│   ├── app.py              <-- Main application server
│   ├── uploaded_videos/    <-- Storage for uploaded videos
│   ├── web_server.py       <-- Web interface server
│   └── whisper_online_server.py <-- Whisper ASR server
├── utils/                  <-- Utility classes and functions
│   ├── chat_history.py
│   ├── logging_utils.py
│   └── response_handler.py
├── web/                    <-- Web interface assets
│   ├── src/                <-- Vue.js components
│   │   ├── App.vue
│   │   ├── components/
│   │   │   ├── Annotation.vue
│   │   │   ├── ChatMessage.vue
│   │   │   ├── Note.vue
│   │   │   ├── PostOpNote.vue
│   │   │   └── VideoCard.vue
│   │   └── main.js
│   ├── static/             <-- CSS, JS, and other static assets
│   │   ├── audio.js
│   │   ├── bootstrap.bundle.min.js
│   │   ├── bootstrap.css
│   │   ├── chat.css
│   │   ├── jquery-3.6.3.min.js
│   │   ├── main.js
│   │   ├── nvidia-logo.png
│   │   ├── styles.css
│   │   ├── tailwind-custom.css
│   │   └── websocket.js
│   └── templates/
│       └── index.html
├── annotations/            <-- Stored procedure annotations
├── uploaded_videos/        <-- Uploaded video storage
├── CLAUDE.md               <-- Guidelines for Claude or other AI assistants
├── README.md               <-- This file
├── package.json            <-- Node.js dependencies and scripts
├── postcss.config.js       <-- PostCSS configuration for Tailwind
├── tailwind.config.js      <-- Tailwind CSS configuration
├── vite.config.js          <-- Vite build configuration
└── requirements.txt        <-- Python dependencies
```

## Recent Updates

* Added robust WebSocket connection handling with automatic reconnection
* Improved video upload and management functionality
* Enhanced post-operation note generation interface
* Modernized UI with Vue.js components
* Added tailored CSS styling with Tailwind
* Implemented development scripts for faster iteration