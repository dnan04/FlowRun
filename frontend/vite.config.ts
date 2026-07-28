import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/flowrun/',
  plugins: [
    vue(),
    {
      name: 'fix-flowrun-missing-slash',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.url && (req.url === '/flowrun' || req.url.startsWith('/flowrun?'))) {
            const redirectUrl = req.url.replace(/^\/flowrun/, '/flowrun/')
            res.writeHead(302, { Location: redirectUrl })
            res.end()
            return
          }
          next()
        })
      }
    }
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/flowrun/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/flowrun/, '')
      }
    }
  }
})
