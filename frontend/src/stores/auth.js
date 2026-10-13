import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

// 鉴权状态管理
export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref(localStorage.getItem('username') || '')
  const role = ref(localStorage.getItem('role') || '')

  const isLoggedIn = computed(() => !!token.value)

  // 登录
  async function login(user, pass) {
    const res = await api.post('/auth/login', { username: user, password: pass })
    token.value = res.access_token
    username.value = res.username
    role.value = res.role
    localStorage.setItem('token', token.value)
    localStorage.setItem('username', username.value)
    localStorage.setItem('role', role.value)
    return res
  }

  // 登出
  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, username, role, isLoggedIn, login, logout }
})
