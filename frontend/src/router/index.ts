import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('../layout/MainLayout.vue'),
      children: [
        { path: '', redirect: '/tasks' },
        { path: '/tasks', component: () => import('../views/TaskCenterView.vue') },
        { path: '/admin/tasks', component: () => import('../views/AdminTaskView.vue') }
      ]
    },
    { path: '/:pathMatch(.*)*', redirect: '/tasks' }
  ]
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  const queryUser = typeof to.query.user === 'string' ? to.query.user.trim() : ''

  if (queryUser) {
    try {
      auth.logout()
      await auth.login(queryUser)
      const query = { ...to.query }
      delete query.user
      return {
        path: auth.isAdmin ? '/admin/tasks' : '/tasks',
        query,
        replace: true
      }
    } catch (error: any) {
      auth.logout()
      ElMessage.error(error?.response?.data?.detail || 'URL 登录失败')
      return false
    }
  }

  if (!auth.user && auth.token) {
    try {
      await auth.loadMe()
    } catch {
      auth.logout()
    }
  }

  if (!auth.token) {
    return false
  }

  if (to.path !== '/tasks' && !auth.isAdmin) {
    return '/tasks'
  }
})

export default router
