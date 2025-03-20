<template>
  <div id="app">
    <!-- Content will be provided by index.html structure -->
  </div>
</template>

<script>
import { defineComponent } from 'vue'
import PostOpNote from './components/PostOpNote.vue'
import ChatMessage from './components/ChatMessage.vue'
import Annotation from './components/Annotation.vue'
import Note from './components/Note.vue'
import VideoCard from './components/VideoCard.vue'

export default defineComponent({
  name: 'App',
  components: {
    PostOpNote,
    ChatMessage,
    Annotation,
    Note,
    VideoCard
  }
})
</script>

<style>
/* No additional styles needed here since we use Tailwind */
</style>