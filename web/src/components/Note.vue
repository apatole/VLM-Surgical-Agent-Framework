<template>
  <div class="bg-dark-800 border border-dark-700 rounded-lg p-3 mb-3 hover:border-primary-600 transition-colors">
    <div class="flex items-start">
      <div class="flex-shrink-0 mr-3">
        <i class="fas fa-sticky-note text-primary-400 mt-1"></i>
      </div>
      <div class="flex-grow">
        <div class="flex justify-between items-start">
          <span class="text-sm font-medium">{{ note.title || 'Untitled Note' }}</span>
          <span class="text-xs text-gray-400">{{ formattedTime }}</span>
        </div>
        <p class="text-sm text-gray-300 mt-1">{{ note.content }}</p>
        
        <div v-if="note.image_url" class="mt-2">
          <img :src="note.image_url" @click="viewImage" class="rounded max-h-32 cursor-pointer hover:opacity-90 transition-opacity border border-dark-600" :alt="note.title">
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Note',
  emits: ['view-image'],
  props: {
    note: {
      type: Object,
      required: true
    }
  },
  computed: {
    formattedTime() {
      // Format timestamp to time or format video_time to MM:SS
      if (this.note.timestamp) {
        return new Date(this.note.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } else if (this.note.video_time) {
        const time = this.note.video_time;
        const minutes = Math.floor(time / 60);
        const seconds = Math.floor(time % 60);
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
      }
      return '';
    }
  },
  methods: {
    viewImage() {
      if (this.note.image_url) {
        this.$emit('view-image', this.note);
      }
    }
  }
}
</script>