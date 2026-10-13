<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <span class="logo-icon">🛒</span>
        <span class="logo-text">商品检索系统</span>
      </div>
      <el-menu :default-active="$route.path" router>
        <template v-for="item in menuItems" :key="item.path">
          <el-menu-item :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="header-title">{{ currentTitle }}</span>
        <div class="user-info">
          <el-tag type="warning" effect="plain" round>{{ auth.username }}（{{ roleLabel }}）</el-tag>
          <el-button type="danger" plain size="small" @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// 角色中文标签
const roleLabel = computed(() => {
  const map = { admin: '管理员', operator: '运营', staff: '店员' }
  return map[auth.role] || auth.role
})

// 菜单项（按角色过滤）
const menuItems = computed(() => {
  const all = [
    { path: '/search', title: '多模态检索', icon: 'Search', roles: ['admin', 'operator', 'staff'] },
    { path: '/camera', title: '摄像头识别', icon: 'Camera', roles: ['admin', 'operator', 'staff'] },
    { path: '/goods', title: '商品列表', icon: 'Goods', roles: ['operator', 'admin'] },
    { path: '/import', title: '批量导入', icon: 'Upload', roles: ['operator', 'admin'] },
    { path: '/tasks', title: '任务管理', icon: 'List', roles: ['operator', 'admin'] },
  ]
  return all.filter((i) => !i.roles || i.roles.includes(auth.role))
})

const currentTitle = computed(() => route.meta.title || '')

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.aside {
  background: #3d2f28;
  color: #fff;
}
.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  background: #2a201b;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.logo-icon {
  font-size: 22px;
}
.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: #f0e0d0;
}
.el-menu {
  background: transparent;
  border: none;
}
:deep(.el-menu-item) {
  color: #d4c5b5;
}
:deep(.el-menu-item:hover) {
  background: #4a3a30 !important;
  color: #fff;
}
:deep(.el-menu-item.is-active) {
  color: #fff;
  background: linear-gradient(90deg, #e8733a 0%, #f0a060 100%) !important;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #f0e6dc;
  background: #fff;
}
.header-title {
  font-size: 18px;
  font-weight: 700;
  color: #3d2f28;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}
.main-content {
  background: #faf6f2;
}
</style>
