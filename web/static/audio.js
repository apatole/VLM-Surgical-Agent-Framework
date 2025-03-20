let audioContext = null;
let mediaStream = null;
let recorder = null;
let audioChunks = [];
let audioWS = null;
let recording = false;

function getWebsocketProtocol() {
    return window.location.protocol === 'https:' ? 'wss://' : 'ws://';
}

async function startAudio() {
    if (recording) return;
    recording = true;

    try {
        // Check if mediaDevices API is available
        if (!navigator.mediaDevices) {
            throw new Error("MediaDevices API not available. This may be because you're not using HTTPS or your browser doesn't support it.");
        }
        
        // Request microphone
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });

        // Use MediaRecorder to capture compressed WebM/Opus
        recorder = new MediaRecorder(mediaStream, { mimeType: "audio/webm" });
        audioChunks = [];

        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                audioChunks.push(e.data);
            }
        };

        recorder.start();
        console.log("MediaRecorder started, mic live.");
    } catch (err) {
        console.error("Error starting audio:", err);
        recording = false;
        // Display a user-friendly message in the UI
        alert("Microphone access error: " + err.message + 
              "\n\nThis may be because:\n" +
              "1. You're not using HTTPS (required for microphone access)\n" +
              "2. You denied microphone permission\n" +
              "3. Your browser doesn't support the MediaDevices API");
        throw err;
    }
}

async function stopAudio() {
    if (!recording) return;
    recording = false;

    try {
        if (recorder && recorder.state !== "inactive") {
            recorder.stop();
            console.log("Recorder stopped.");
        }

        // Wait briefly for final data
        await new Promise(resolve => setTimeout(resolve, 100));

        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }

        // Now send the entire .webm chunk via a one-shot WebSocket
        if (audioChunks.length > 0) {
            console.log("Total recorded chunks:", audioChunks.length);
            const fullBlob = new Blob(audioChunks, { type: "audio/webm" });
            const arrayBuf = await fullBlob.arrayBuffer();

            // Capture a frame to send along with the audio, store in sessionStorage for use later
            if (typeof captureVideoFrame === 'function') {
                const frameData = captureVideoFrame();
                if (frameData) {
                    console.log("Captured frame for audio processing");
                    sessionStorage.setItem('lastCapturedFrame', frameData);
                }
            }

            const audioUrl = `${getWebsocketProtocol()}${window.location.hostname}:49001`;
            audioWS = new WebSocket(audioUrl);
            audioWS.binaryType = "arraybuffer";

            audioWS.onopen = () => {
                console.log("Audio WS connected (one-shot). Sending .webm data...");
                audioWS.send(arrayBuf);
                audioWS.close();
            };

            audioWS.onclose = () => {
                console.log("One-shot audio WebSocket closed.");
            };
        } else {
            console.log("No audio chunks available to send.");
        }

        console.log("Stopped audio capture fully.");
    } catch (err) {
        console.error("Error stopping audio:", err);
    }
}
