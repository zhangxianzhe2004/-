<template>
  <div class="goods-edit">
    <el-card class="edit-card">
      <template #header>
        <div class="card-header">
          <el-icon><Edit /></el-icon>
          <span>编辑商品：{{ form.barcode }}</span>
        </div>
      </template>
      <el-form :model="form" label-width="100px" v-loading="loading" class="edit-form">
        <el-form-item label="条码">
          <el-input v-model="form.barcode" disabled />
        </el-form-item>
        <el-form-item label="商品名称">
          <el-input v-model="form.goods_name" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" />
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="form.spec" />
        </el-form-item>
        <el-form-item label="零售价">
          <el-input-number v-model="form.retail_price" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="进价">
          <el-input-number v-model="form.cost_price" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="货架号">
          <el-input v-model="form.shelf_no" />
        </el-form-item>
        <el-form-item label="库存">
          <el-input-number v-model="form.stock" :min="0" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input v-model="form.supplier" />
        </el-form-item>
        <el-form-item label="商品描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSave" size="large">
            <el-icon style="margin-right:4px"><Check /></el-icon>保存
          </el-button>
          <el-button @click="$router.back()" size="large">
            <el-icon style="margin-right:4px"><Back /></el-icon>返回
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const form = reactive({})

async function loadGoods() {
  loading.value = true
  try {
    const res = await api.get(`/goods/${route.params.barcode}`)
    Object.assign(form, res)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  try {
    await api.put(`/goods/${route.params.barcode}`, form)
    ElMessage.success('保存成功')
    router.push('/goods')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(loadGoods)
</script>

<style scoped>
.goods-edit { padding: 20px; }
.edit-card {
  border-radius: 12px;
  max-width: 700px;
  margin: 0 auto;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #3d2f28;
}
.edit-form { padding: 12px 8px 0; }
</style>
