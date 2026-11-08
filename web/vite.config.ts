import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: { assetsDir: 'app-assets' },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/Images': 'http://127.0.0.1:8000',
      '/assets': 'http://127.0.0.1:8000',
    },
  },
});
