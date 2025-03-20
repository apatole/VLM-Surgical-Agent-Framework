import { createApp } from 'vue'
import axios from 'axios'

// Import components
import PostOpNote from './components/PostOpNote.vue'
import ChatMessage from './components/ChatMessage.vue'
import Annotation from './components/Annotation.vue'
import Note from './components/Note.vue'
import VideoCard from './components/VideoCard.vue'

// Create Vue app
const app = createApp({
  // Root app component
  data() {
    return {
      // Chat state
      chatMessages: [],
      currentMessage: '',
      
      // Annotations state
      annotations: [],
      
      // Notes state
      notes: [],
      
      // Summary state
      postOpNote: null,
      postOpError: null,
      
      // Video state
      videos: [],
      selectedVideo: null,
      searchQuery: '',
      
      // UI state
      activeTab: 'chat',
      isMicActive: false,
      isTtsEnabled: false,
      apiKey: '',
      
      // Websocket
      ws: null,
      wsConnected: false
    }
  },
  computed: {
    filteredVideos() {
      if (!this.searchQuery) return this.videos;
      const query = this.searchQuery.toLowerCase();
      return this.videos.filter(video => 
        video.filename.toLowerCase().includes(query)
      );
    }
  },
  mounted() {
    // Initialize websocket connection
    this.initWebSocket();
    
    // Load videos
    this.fetchVideos();
    
    // Initialize time display for video
    this.initVideoTimeDisplay();
    
    // Set current time in welcome message
    document.getElementById('welcome-time').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    // Initialize event listeners
    this.initEventListeners();
  },
  methods: {
    // Websocket methods
    initWebSocket() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host.split(':')[0]}:49000`;
      
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        this.wsConnected = true;
        console.log('WebSocket connected');
      };
      
      this.ws.onmessage = (event) => {
        this.handleServerMessage(event);
      };
      
      this.ws.onclose = () => {
        this.wsConnected = false;
        console.log('WebSocket disconnected');
        // Attempt to reconnect after 3 seconds
        setTimeout(() => this.initWebSocket(), 3000);
      };
    },
    
    handleServerMessage(event) {
      try {
        const message = JSON.parse(event.data);
        
        // Handle different message types
        if (message.text) {
          // Add chat message
          this.addChatMessage(message.text, 'agent');
        }
        
        if (message.annotation) {
          // Add annotation
          this.addAnnotation(message.annotation);
        }
        
        if (message.note) {
          // Add note
          this.addNote(message.note);
        }
        
        if (message.current_phase) {
          // Update current phase
          document.getElementById('current-phase').textContent = message.current_phase;
        }
        
        if (message.video_updated && message.video_src) {
          // Update video source
          const video = document.getElementById('surgery-video');
          video.src = message.video_src;
          video.load();
        }
        
        // Handle TTS if enabled
        if (message.text && this.isTtsEnabled) {
          this.generateSpeech(message.text);
        }
      } catch (err) {
        console.error('Error handling WebSocket message:', err);
      }
    },
    
    // Chat methods
    sendChatMessage() {
      if (!this.currentMessage.trim()) return;
      
      // Add message to chat history
      this.addChatMessage(this.currentMessage, 'user');
      
      // Send message over websocket
      if (this.wsConnected) {
        this.ws.send(JSON.stringify({ text: this.currentMessage }));
      }
      
      // Clear input
      this.currentMessage = '';
    },
    
    addChatMessage(content, role) {
      const message = {
        id: Date.now(),
        content,
        role,
        timestamp: Date.now()
      };
      
      this.chatMessages.push(message);
      
      // Scroll to bottom of chat
      this.$nextTick(() => {
        const container = document.getElementById('chat-history-container');
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    },
    
    // Annotation methods
    addAnnotation(annotation) {
      // Add timestamp if not present
      if (!annotation.timestamp) {
        annotation.timestamp = Date.now();
      }
      
      this.annotations.push(annotation);
      
      // Update annotation count
      document.querySelectorAll('.annotation-count').forEach(el => {
        el.textContent = this.annotations.length;
      });
    },
    
    // Note methods
    addNote(note) {
      // Add timestamp if not present
      if (!note.timestamp) {
        note.timestamp = Date.now();
      }
      
      this.notes.push(note);
      
      // Update note count
      document.querySelectorAll('.notes-count').forEach(el => {
        el.textContent = this.notes.length;
      });
    },
    
    saveManualNote() {
      const title = document.getElementById('note-title').value.trim();
      const content = document.getElementById('note-content').value.trim();
      const message = document.getElementById('note-message').value.trim();
      const previewContainer = document.getElementById('note-image-preview-container');
      
      if (!content) {
        alert('Please enter note content');
        return;
      }
      
      // Create note object
      const note = {
        title: title || 'Manual Note',
        content,
        timestamp: Date.now(),
        manual: true
      };
      
      // Add image if available
      if (previewContainer && !previewContainer.classList.contains('hidden')) {
        const preview = document.getElementById('note-image-preview');
        if (preview && preview.src) {
          note.image_url = preview.src;
        }
      }
      
      // Add the note
      this.addNote(note);
      
      // Send the note to the server
      if (this.wsConnected) {
        this.ws.send(JSON.stringify({ note }));
      }
      
      // Send additional message if provided
      if (message && this.wsConnected) {
        this.ws.send(JSON.stringify({ text: message }));
        this.addChatMessage(message, 'user');
      }
      
      // Close modal
      this.closeModal('addNoteModal');
      
      // Reset form
      document.getElementById('note-title').value = '';
      document.getElementById('note-content').value = '';
      document.getElementById('note-message').value = '';
      if (previewContainer) {
        previewContainer.classList.add('hidden');
      }
    },
    
    // Summary methods
    generateSummary() {
      // Clear previous data
      this.postOpNote = null;
      this.postOpError = null;
      
      // Gather all current annotations and notes to send to the server
      const data = {
        annotations: this.annotations,
        notes: this.notes,
        video_duration: document.getElementById('video-duration')?.textContent || 'Unknown'
      };
      
      // Show loading state in the summary container
      document.getElementById('summary-container').innerHTML = `
        <div class="text-center p-5">
          <div class="animate-spin rounded-full h-10 w-10 border-4 border-t-primary-400 border-dark-600 mb-4 mx-auto"></div>
          <p class="text-white">Generating procedure summary...</p>
        </div>
      `;
      
      // Request summary from server
      axios.post('/api/generate_post_op_note', data)
        .then(response => {
          if (response.data.post_op_note) {
            this.postOpNote = response.data.post_op_note;
            this.postOpError = null;
            
            // Update summary container with Vue component
            document.getElementById('summary-container').innerHTML = `
              <div id="post-op-note-container"></div>
            `;
            
            // Mount the PostOpNote component to the container
            const postOpNoteContainer = document.getElementById('post-op-note-container');
            if (postOpNoteContainer) {
              const postOpNoteInstance = createApp({
                components: { 'post-op-note': PostOpNote },
                data() {
                  return {
                    note: this.postOpNote
                  };
                },
                template: '<post-op-note :post-op-note="note" />'
              });
              
              postOpNoteInstance.mount(postOpNoteContainer);
            }
          } else {
            this.postOpError = 'No procedure data available';
            document.getElementById('summary-container').innerHTML = `
              <div class="text-center p-5">
                <div class="text-red-400 text-lg mb-2">Error</div>
                <p class="text-gray-300">No procedure data available for summary generation.</p>
              </div>
            `;
          }
        })
        .catch(error => {
          console.error('Error generating summary:', error);
          this.postOpError = error.response?.data?.error || 'Failed to generate summary';
          document.getElementById('summary-container').innerHTML = `
            <div class="text-center p-5">
              <div class="text-red-400 text-lg mb-2">Error</div>
              <p class="text-gray-300">${this.postOpError}</p>
            </div>
          `;
        });
    },
    
    // Video methods
    fetchVideos() {
      axios.get('/api/videos')
        .then(response => {
          this.videos = response.data.videos || [];
          document.getElementById('video-loading').classList.add('hidden');
          
          if (this.videos.length === 0) {
            document.getElementById('no-videos').classList.remove('hidden');
          }
        })
        .catch(error => {
          console.error('Error fetching videos:', error);
          document.getElementById('video-loading').classList.add('hidden');
          document.getElementById('no-videos').classList.remove('hidden');
        });
    },
    
    selectVideo(video) {
      this.selectedVideo = video;
      
      // Close modal
      this.closeModal('videoSelectModal');
      
      // Update video
      axios.post('/api/select_video', { filename: video.filename })
        .then(response => {
          console.log('Video selected:', response.data);
        })
        .catch(error => {
          console.error('Error selecting video:', error);
        });
    },
    
    uploadVideo() {
      const fileInput = document.getElementById('video-upload');
      if (!fileInput.files.length) {
        alert('Please select a video file first');
        return;
      }
      
      const formData = new FormData();
      formData.append('video', fileInput.files[0]);
      
      // Show loading state
      const uploadBtn = document.querySelector('button[onclick="uploadVideo()"]');
      const originalText = uploadBtn.innerHTML;
      uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Uploading...';
      uploadBtn.disabled = true;
      
      // Upload video
      axios.post('/api/upload_video', formData)
        .then(response => {
          console.log('Video uploaded:', response.data);
          
          // Reset file input
          fileInput.value = '';
          document.querySelector('.file-name').textContent = 'Select video file...';
          
          // Reset button
          uploadBtn.innerHTML = originalText;
          uploadBtn.disabled = false;
          
          // Refresh video list
          this.fetchVideos();
        })
        .catch(error => {
          console.error('Error uploading video:', error);
          alert('Error uploading video');
          
          // Reset button
          uploadBtn.innerHTML = originalText;
          uploadBtn.disabled = false;
        });
    },
    
    // UI methods
    initEventListeners() {
      // Initialize tab switching
      document.querySelectorAll('[data-tab-target]').forEach(button => {
        button.addEventListener('click', () => {
          const targetId = button.getAttribute('data-tab-target');
          this.switchTab(targetId);
        });
      });
      
      // Initialize modal triggers
      document.querySelectorAll('[data-modal-target]').forEach(button => {
        button.addEventListener('click', () => {
          const modalId = button.getAttribute('data-modal-target');
          this.openModal(modalId);
        });
      });
      
      // Initialize modal close buttons
      document.querySelectorAll('[data-close-modal]').forEach(button => {
        button.addEventListener('click', () => {
          const modal = button.closest('.modal');
          if (modal) {
            this.closeModal(modal.id);
          }
        });
      });
      
      // Initialize file input display
      const fileInput = document.getElementById('video-upload');
      if (fileInput) {
        fileInput.addEventListener('change', () => {
          const fileName = fileInput.files.length ? 
            fileInput.files[0].name : 'Select video file...';
          document.querySelector('.file-name').textContent = fileName;
        });
      }
      
      // Initialize TTS toggle
      const ttsToggle = document.getElementById('ttsEnable');
      if (ttsToggle) {
        ttsToggle.addEventListener('change', () => {
          this.isTtsEnabled = ttsToggle.checked;
          
          // Toggle visual indication
          const dot = document.querySelector('.toggle-switch .dot');
          if (this.isTtsEnabled) {
            dot.classList.add('translate-x-4');
          } else {
            dot.classList.remove('translate-x-4');
          }
        });
      }
      
      // Initialize textarea auto-resize
      const textarea = document.getElementById('chat-message-input');
      if (textarea) {
        textarea.addEventListener('input', () => {
          textarea.style.height = 'auto';
          textarea.style.height = (textarea.scrollHeight) + 'px';
        });
      }
    },
    
    switchTab(tabId) {
      // Hide all tab panes
      document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
        pane.style.display = 'none';
      });
      
      // Deactivate all tab buttons
      document.querySelectorAll('[role="tab"]').forEach(btn => {
        btn.classList.remove('active');
        btn.classList.remove('border-b-2');
        btn.classList.remove('border-primary-500');
        btn.classList.remove('bg-dark-800');
      });
      
      // Show the selected tab pane
      const selectedPane = document.getElementById(tabId);
      if (selectedPane) {
        selectedPane.classList.add('active');
        selectedPane.style.display = 'block';
        
        // Save active tab
        this.activeTab = tabId;
      }
      
      // Activate the clicked tab button
      const tabButton = document.querySelector(`[data-tab-target="${tabId}"]`);
      if (tabButton) {
        tabButton.classList.add('active');
        tabButton.classList.add('border-b-2');
        tabButton.classList.add('border-primary-500');
        tabButton.classList.add('bg-dark-800');
      }
    },
    
    openModal(modalId) {
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.classList.remove('hidden');
        
        // If it's the video modal, fetch the latest videos
        if (modalId === 'videoSelectModal') {
          this.fetchVideos();
        }
      }
    },
    
    closeModal(modalId) {
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.classList.add('hidden');
      }
    },
    
    // Utility methods
    initVideoTimeDisplay() {
      const video = document.getElementById('surgery-video');
      const currentTimeElement = document.getElementById('video-current-time');
      const durationElement = document.getElementById('video-duration');
      
      if (video && currentTimeElement && durationElement) {
        // Update current time
        video.addEventListener('timeupdate', () => {
          const minutes = Math.floor(video.currentTime / 60);
          const seconds = Math.floor(video.currentTime % 60);
          currentTimeElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        });
        
        // Update duration when metadata is loaded
        video.addEventListener('loadedmetadata', () => {
          const minutes = Math.floor(video.duration / 60);
          const seconds = Math.floor(video.duration % 60);
          durationElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        });
      }
    },
    
    toggleMic() {
      this.isMicActive = !this.isMicActive;
      
      const micBtn = document.getElementById('mic-btn');
      if (micBtn) {
        if (this.isMicActive) {
          micBtn.innerHTML = '<i class="fas fa-stop-circle mr-1.5"></i> <span>Stop</span>';
          micBtn.classList.add('bg-red-600');
          micBtn.classList.remove('bg-primary-600');
          // Start audio recording
          startRecording();
        } else {
          micBtn.innerHTML = '<i class="fas fa-microphone mr-1.5"></i> <span>Start Mic</span>';
          micBtn.classList.remove('bg-red-600');
          micBtn.classList.add('bg-primary-600');
          // Stop audio recording
          stopRecording();
        }
      }
    },
    
    generateSpeech(text) {
      // Request TTS from server
      axios.post('/api/tts', { 
        text,
        api_key: this.apiKey
      })
      .then(response => {
        if (response.data.audio_base64) {
          // Play the audio
          const audio = new Audio(`data:audio/mp3;base64,${response.data.audio_base64}`);
          audio.play();
        }
      })
      .catch(error => {
        console.error('Error generating speech:', error);
      });
    },
    
    captureFrame() {
      const video = document.getElementById('surgery-video');
      if (!video) return null;
      
      // Create canvas and draw video frame
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      // Convert to base64
      return canvas.toDataURL('image/jpeg');
    },
    
    captureAndStoreFrame() {
      const imageData = this.captureFrame();
      if (!imageData) return;
      
      // Open image viewer modal
      this.openImageViewer({
        image_url: imageData,
        title: 'Captured Frame',
        timestamp: new Date().toLocaleString(),
        type: 'Capture'
      });
    },
    
    captureForNote() {
      const imageData = this.captureFrame();
      if (!imageData) return;
      
      // Display in note preview
      const preview = document.getElementById('note-image-preview');
      const container = document.getElementById('note-image-preview-container');
      
      if (preview && container) {
        preview.src = imageData;
        container.classList.remove('hidden');
      }
    },
    
    openImageViewer(item) {
      // Populate modal with image data
      document.getElementById('modal-image').src = item.image_url;
      document.getElementById('image-title').textContent = item.title || 'Image Viewer';
      document.getElementById('image-timestamp').textContent = item.timestamp || '';
      document.getElementById('image-type').textContent = item.type || '';
      document.getElementById('image-description').textContent = item.content || '';
      
      // Setup download button
      const downloadBtn = document.getElementById('download-image-btn');
      if (downloadBtn) {
        downloadBtn.onclick = () => {
          const link = document.createElement('a');
          link.href = item.image_url;
          link.download = `image_${new Date().getTime()}.jpg`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        };
      }
      
      // Open modal
      this.openModal('imageViewerModal');
    }
  }
});

// Register components
app.component('post-op-note', PostOpNote);
app.component('chat-message', ChatMessage);
app.component('annotation-item', Annotation);
app.component('note-item', Note);
app.component('video-card', VideoCard);

// Mount the app
app.mount('#app');