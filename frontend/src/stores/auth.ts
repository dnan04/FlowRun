import { defineStore } from 'pinia'
import http from '../api/http'

export type CurrentUser = {
  id: number
  username: string
  email?: string
  fullname?: string
  roles: string[]
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('data_runner_token') || '',
    user: null as CurrentUser | null
  }),
  getters: {
    isAdmin: (state) => state.user?.roles?.includes('ADMIN') ?? false
  },
  actions: {
    async login(username: string) {
      const { data } = await http.post('/auth/login', { username: username.trim() })
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('data_runner_token', data.access_token)
    },
    async loadMe() {
      if (!this.token) {
        return
      }
      const { data } = await http.get('/auth/me')
      this.user = data
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('data_runner_token')
    }
  }
})
