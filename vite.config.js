import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/geomancer-ml-decision-making/',
  build: {
    outDir: 'docs',
    emptyOutDir: false, // Don't delete existing assets like images
    rollupOptions: {
      input: {
        main: 'index.html'
      }
    }
  },
  server: {
    open: true
  }
})
