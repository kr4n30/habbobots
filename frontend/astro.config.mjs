import { defineConfig } from 'astro/config';

export default defineConfig({
  output: 'static',
  vite: {
    server: {
      proxy: {
        // Durante dev: /api/* → http://localhost:3001/*
        '/api': {
          target: 'http://localhost:3001',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  },
});
