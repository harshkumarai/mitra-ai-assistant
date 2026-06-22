import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// - Production build: assets are served at /static/ by FastAPI (base: '/static/')
// - Dev server: Vite serves at root (/), with proxy to FastAPI at :8001 for API/WS
export default defineConfig(({ command }) => ({
  plugins: [react()],
  // Only apply the /static/ base when building for production.
  // In dev mode ('serve') the Vite dev server handles assets at /.
  base: command === 'build' ? '/static/' : '/',
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://127.0.0.1:8001',
        ws: true,
        changeOrigin: true,
      },
    },
  },
}))
