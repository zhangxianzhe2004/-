<template>
  <div class="login-container">
    <!-- 超市场景背景图 -->
    <div class="login-bg"></div>
    <div class="login-overlay"></div>

    <!-- 登录卡片 -->
    <el-card class="login-card">
      <div class="login-header">
        <div class="login-logo">🛒</div>
        <div class="login-title">超市商品多模态检索系统</div>
        <div class="login-subtitle">Multi-Modal Goods Retrieval System</div>
      </div>
      <el-form :model="form" @submit.prevent="handleLogin" class="login-form">
        <el-form-item>
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            prefix-icon="User"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            size="large"
            class="login-btn"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-accounts">
        <div class="account-row" v-for="a in accounts" :key="a.user">
          <span class="account-tag" :style="{ background: a.color }">{{ a.role }}</span>
          <span class="account-info">{{ a.user }} / 123456</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ username: 'admin', password: '123456' })

const accounts = [
  { user: 'admin', role: '管理员', color: '#e8733a' },
  { user: 'operator', role: '运营', color: '#67b680' },
  { user: 'staff', role: '店员', color: '#5b8dbf' },
]

async function handleLogin() {
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    ElMessage.error(e.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  position: relative;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
/* 超市背景图 */
.login-bg {
  position: absolute;
  inset: 0;
  background-image: url('../assets/supermarket-bg.jpg');
  background-size: cover;
  background-position: center;
  transform: scale(1.05);
}
/* 半透明遮罩，让卡片更突出 */
.login-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(61,47,40,0.65) 0%, rgba(232,115,58,0.35) 100%);
}
/* 登录卡片 */
.login-card {
  position: relative;
  z-index: 1;
  width: 420px;
  border: none;
  border-radius: 16px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(10px);
  background: rgba(255, 255, 255, 0.96);
}
.login-header {
  text-align: center;
  padding: 24px 0 12px;
}
.login-logo {
  font-size: 48px;
  margin-bottom: 8px;
}
.login-title {
  font-size: 22px;
  font-weight: 700;
  color: #3d2f28;
}
.login-subtitle {
  font-size: 12px;
  color: #b0a090;
  margin-top: 4px;
  letter-spacing: 1px;
}
.login-form {
  padding: 8px 32px 0;
}
.login-btn {
  width: 100%;
  font-size: 16px;
  letter-spacing: 4px;
}
.login-accounts {
  padding: 12px 32px 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.account-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.account-tag {
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  color: #fff;
  font-weight: 600;
}
.account-info {
  font-size: 13px;
  color: #8a7a6a;
}
</style>
