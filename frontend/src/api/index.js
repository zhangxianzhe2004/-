import axios from 'axios'

// Axios 实例：统一配置 baseURL + 请求拦截（带 Token）
const instance = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 请求拦截：自动带 JWT Token
instance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截：统一错误处理
instance.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        // 未登录或 token 失效
        localStorage.removeItem('token')
        localStorage.removeItem('username')
        localStorage.removeItem('role')
        window.location.href = '/login'
      }
      return Promise.reject(new Error(data.detail || `请求失败 (${status})`))
    }
    return Promise.reject(error)
  }
)

export default instance
