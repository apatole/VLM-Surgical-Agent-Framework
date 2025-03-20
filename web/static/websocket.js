let websocket = null;
let reconnectInterval = null;
let reconnectAttempts = 0;
let maxReconnectAttempts = 5;
let reconnectDelay = 3000; // Start with 3 seconds
let onMessageCallbackStore = null;
let currentPort = 49000;

function getWebsocketProtocol() {
  return window.location.protocol === 'https:' ? 'wss://' : 'ws://';
}

function getWebsocketURL(port=49000) {
  // For development with Tailscale, ensure we're using the same hostname
  // that was used to access the main page
  return `${getWebsocketProtocol()}${window.location.hostname}:${port}`;
}

// Attempts to reconnect to the WebSocket server
function reconnectWebsocket() {
  if (reconnectAttempts >= maxReconnectAttempts) {
    console.warn(`Maximum reconnect attempts (${maxReconnectAttempts}) reached. Stopping reconnection.`);
    clearInterval(reconnectInterval);
    reconnectInterval = null;
    reconnectAttempts = 0;
    return;
  }
  
  reconnectAttempts++;
  console.log(`Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`);
  connectWebsocket(currentPort, onMessageCallbackStore);
}

// Connects to the websocket server on a given port and sets up event handlers.
function connectWebsocket(port=49000, onMessageCallback=null) {
  // Store these for reconnection
  currentPort = port;
  onMessageCallbackStore = onMessageCallback;
  
  // Clear any existing reconnect intervals
  if (reconnectInterval) {
    clearInterval(reconnectInterval);
    reconnectInterval = null;
  }
  
  const url = getWebsocketURL(port);
  console.log("Attempting WebSocket connection to:", url);
  
  // Close existing connection if any
  if (websocket && websocket.readyState !== WebSocket.CLOSED) {
    websocket.close();
  }
  
  websocket = new WebSocket(url);

  websocket.onopen = () => {
    console.log("WebSocket connected to", url);
    reconnectAttempts = 0; // Reset attempts on successful connection
  };

  websocket.onmessage = (event) => {
    // Reset reconnect attempts on successful message receipt
    reconnectAttempts = 0;
    
    console.log("Message received from server:", event.data);
    try {
      const msg = JSON.parse(event.data);
      // If we have a callback, call it
      if (onMessageCallback) onMessageCallback(msg);
    } catch (e) {
      console.error("Failed to parse WebSocket message as JSON:", e, event.data);
    }
  };

  websocket.onerror = (err) => {
    console.error("WebSocket error:", err);
  };

  websocket.onclose = (event) => {
    console.log(`WebSocket closed. Code: ${event.code}, Reason: ${event.reason}`);
    
    // Don't attempt to reconnect if closed normally (1000)
    if (event.code !== 1000 && !reconnectInterval) {
      console.log("Setting up reconnection timer...");
      reconnectInterval = setInterval(reconnectWebsocket, reconnectDelay);
    }
  };
  
  // Set up a heartbeat to keep the connection alive
  // This sends a small payload every 20 seconds to prevent timeouts
  const heartbeatInterval = setInterval(() => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({ type: "heartbeat" }));
    } else if (websocket.readyState !== WebSocket.CONNECTING) {
      clearInterval(heartbeatInterval);
    }
  }, 20000); // Send heartbeat every 20 seconds
}

// Sends a JSON payload over the WebSocket
function sendJSON(payload) {
  if (!websocket || websocket.readyState !== WebSocket.OPEN) {
    console.warn("WebSocket not open. Unable to send message:", payload);
    // Attempt to reconnect if not already in progress
    if (!reconnectInterval && reconnectAttempts < maxReconnectAttempts) {
      reconnectWebsocket();
    }
    return;
  }
  console.log("Sending JSON message:", payload);
  websocket.send(JSON.stringify(payload));
}