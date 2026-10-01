import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  base: '/admin/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 41003,
    proxy: {
      '/0x': {
        target: 'http://localhost:41002',
        changeOrigin: true
      }
    }
  },
  preview: {
    port: 41004
  },
  build: {
    outDir: '../gateway/static',
    emptyOutDir: true
  }
})
