<template>
  <div class="bg-dark-800 border border-dark-700 rounded-lg p-3 mb-3 hover:border-primary-600 transition-colors">
    <div class="flex items-start">
      <div class="flex-shrink-0 mr-3">
        <i class="fas fa-tag text-primary-400 mt-1"></i>
      </div>
      <div class="flex-grow">
        <div class="flex justify-between items-start">
          <div>
            <span class="text-sm font-medium">{{ annotation.type }}</span>
            <span v-if="annotation.confidence" class="ml-2 text-xs px-2 py-0.5 bg-primary-700 text-white rounded-full">
              {{ (annotation.confidence * 100).toFixed(0) }}%
            </span>
          </div>
          <span class="text-xs text-gray-400">{{ formattedTime }}</span>
        </div>
        <p class="text-sm text-gray-300 mt-1">{{ annotation.content }}</p>
        
        <div v-if="annotation.image_url" class="mt-2">
          <img :src="annotation.image_url" @click="viewImage" class="rounded max-h-32 cursor-pointer hover:opacity-90 transition-opacity border border-dark-600" :alt="annotation.type">
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Annotation',
  emits: ['view-image'],
  props: {
    annotation: {
      type: Object,
      required: true
    }
  },
  computed: {
    formattedTime() {
      // Format the video_time (seconds) to MM:SS format
      const time = this.annotation.video_time || 0;
      const minutes = Math.floor(time / 60);
      const seconds = Math.floor(time % 60);
      return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
  },
  methods: {
    viewImage() {
      // Emit an event to handle the image viewing
      // The parent component will handle this, potentially showing a modal
      this.$emit('view-image', this.annotation);
    }
  }
}
</script>