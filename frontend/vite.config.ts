import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// In dev, /api is proxied to the FastAPI backend so the browser sees one origin
// (the backend has no CORS middleware). Override the target with API_PROXY_TARGET.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icons/apple-touch-icon.png', 'icons/favicon.svg'],
      manifest: {
        name: 'Rift Fantasy',
        short_name: 'Rift Fantasy',
        description: 'Fantasy leagues for League of Legends esports with your friends.',
        theme_color: '#0b0f1a',
        background_color: '#0b0f1a',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // App shell is precached; API calls always go to the network so draft
        // boards and trades are never stale.
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [{ urlPattern: ({ url }: { url: URL }) => url.pathname.startsWith('/api/'), handler: 'NetworkOnly' }],
      },
    }),
  ],
  server: {
    host: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
  preview: {
    host: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
    },
  },
})
