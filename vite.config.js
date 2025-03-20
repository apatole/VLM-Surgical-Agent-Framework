import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './web/src'),
    },
  },
  root: './web',
  publicDir: './static',
  build: {
    outDir: '../dist',
    assetsDir: 'assets',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8050',
        changeOrigin: true,
      },
      '/videos': {
        target: 'http://localhost:8050',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:49000',
        ws: true,
      },
    },
    watch: {
      usePolling: true,
    },
  },
})