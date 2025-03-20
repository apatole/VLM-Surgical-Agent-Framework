<template>
  <div 
    class="bg-dark-800 border border-dark-700 rounded-lg overflow-hidden hover:border-primary-500 transition-all duration-200 cursor-pointer flex flex-col"
    :class="{ 'border-primary-400 ring-2 ring-primary-400': isSelected }"
    @click="selectVideo">
    <div class="h-24 bg-dark-900 flex items-center justify-center overflow-hidden">
      <!-- This would be a video thumbnail if available -->
      <i class="fas fa-film text-4xl text-primary-400"></i>
    </div>
    <div class="p-3">
      <div class="flex items-start justify-between">
        <div class="truncate pr-2">
          <h3 class="font-medium text-sm truncate">{{ video.filename }}</h3>
        </div>
        <span v-if="isSelected" class="flex-shrink-0 text-xs px-1.5 py-0.5 bg-primary-500 rounded-full text-white">
          Selected
        </span>
      </div>
      
      <div class="mt-2 flex items-center justify-between text-xs">
        <span class="text-gray-400">{{ formattedDate }}</span>
        <span class="text-gray-400">{{ formattedSize }}</span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'VideoCard',
  emits: ['select'],
  props: {
    video: {
      type: Object,
      required: true
    },
    isSelected: {
      type: Boolean,
      default: false
    }
  },
  computed: {
    formattedDate() {
      return new Date(this.video.modified * 1000).toLocaleDateString();
    },
    formattedSize() {
      // Format the size in MB
      const sizeInMB = (this.video.size / (1024 * 1024)).toFixed(1);
      return `${sizeInMB} MB`;
    }
  },
  methods: {
    selectVideo() {
      this.$emit('select', this.video);
    }
  }
}
</script>