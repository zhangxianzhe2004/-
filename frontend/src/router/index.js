import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// 路由表：登录页 + 主布局（含子路由）
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    redirect: '/search',
    children: [
      {
        path: 'search',
        name: 'SearchTest',
        component: () => import('../views/SearchTest.vue'),
        meta: { title: '多模态检索', icon: 'Search' },
      },
      {
        path: 'camera',
        name: 'CameraSearch',
        component: () => import('../views/CameraSearch.vue'),
        meta: { title: '摄像头识别', icon: 'Camera' },
      },
      {
        path: 'goods',
        name: 'GoodsList',
        component: () => import('../views/GoodsList.vue'),
        meta: { title: '商品列表', icon: 'Goods' },
      },
      {
        path: 'goods/edit/:barcode',
        name: 'GoodsEdit',
        component: () => import('../views/GoodsEdit.vue'),
        meta: { title: '编辑商品', hidden: true },
      },
      {
        path: 'import',
        name: 'ImportTask',
        component: () => import('../views/ImportTask.vue'),
        meta: { title: '批量导入', icon: 'Upload', roles: ['operator', 'admin'] },
      },
      {
        path: 'tasks',
        name: 'TaskList',
        component: () => import('../views/TaskList.vue'),
        meta: { title: '任务管理', icon: 'List', roles: ['operator', 'admin'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：登录态校验 + 角色权限
router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    next()
    return
  }
  if (!auth.token) {
    next('/login')
    return
  }
  // 角色校验
  if (to.meta.roles && !to.meta.roles.includes(auth.role)) {
    next('/search')
    return
  }
  next()
})

export default router
