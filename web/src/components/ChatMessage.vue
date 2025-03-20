<template>
  <div :class="['message', { 'agent-message': isAgent, 'user-message': !isAgent }]">
    <div class="flex items-center justify-between mb-0 -mt-1 -mx-1">
      <span class="flex items-center">
        <span :class="['avatar-icon', isAgent ? 'bg-success-600' : 'bg-primary-600']">
          <i :class="isAgent ? 'fas fa-robot' : 'fas fa-user'"></i>
        </span>
        <span :class="['text-[11px]', isAgent ? 'text-success-300/90' : 'text-primary-300/90']">
          {{ isAgent ? 'AI Assistant' : 'You' }}
        </span>
      </span>
      <span class="text-[10px] text-gray-400/80">{{ formattedTime }}</span>
    </div>
    <div class="message-content">
      <p v-html="formattedContent"></p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ChatMessage',
  // Add $emit type for TypeScript support
  emits: [],
  props: {
    message: {
      type: Object,
      required: true
    }
  },
  computed: {
    isAgent() {
      return this.message.role === 'agent' || this.message.role === 'assistant';
    },
    formattedTime() {
      const timestamp = this.message.timestamp || Date.now();
      return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },
    formattedContent() {
      // Replace newlines with <br> tags for proper HTML rendering
      if (!this.message.content) {
        console.warn('Message content is undefined or null', this.message);
        return '';
      }
      return this.message.content.replace(/\n/g, '<br>');
    }
  },
  mounted() {
    console.log('ChatMessage mounted with message:', this.message);
  }
}
</script>

<style scoped>
.message {
  margin-bottom: 1rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  position: relative;
}

.user-message {
  background-color: rgba(var(--color-primary-700), 0.3);
  border: 1px solid rgba(var(--color-primary-600), 0.3);
}

.agent-message {
  background-color: rgba(var(--color-dark-800), 0.8);
  border: 1px solid rgba(var(--color-success-900), 0.3);
}

.avatar-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  margin-right: 5px;
}

.message-content {
  margin-top: 0.5rem;
  word-break: break-word;
}
</style>