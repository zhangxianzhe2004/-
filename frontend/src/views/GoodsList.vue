<template>
  <div class="goods-list">
    <el-card class="list-card">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="商品名称/条码" clearable style="width: 240px" @keyup.enter="loadData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-input v-model="category" placeholder="分类" clearable style="width: 160px; margin-left: 10px" @keyup.enter="loadData">
          <template #prefix><el-icon><Folder /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="loadData" style="margin-left: 10px">
          <el-icon style="margin-right:4px"><Search /></el-icon>查询
        </el-button>
      </div>
      <el-table :data="list" v-loading="loading" style="margin-top: 16px" row-class-name="table-row">
        <el-table-column label="商品图片" width="90">
          <template #default="{ row }">
            <el-image v-if="row.image_path" :src="imgUrl(row.image_path)" style="width: 64px; height: 64px" fit="cover" class="goods-thumb" />
          </template>
        </el-table-column>
        <el-table-column prop="barcode" label="条码" width="150" />
        <el-table-column prop="goods_name" label="商品名称" />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="spec" label="规格" width="120" />
        <el-table-column prop="retail_price" label="零售价" width="100">
          <template #default="{ row }">
            <span class="price-text">¥{{ row.retail_price }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="shelf_no" label="货架" width="80" />
        <el-table-column prop="stock" label="库存" width="80" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" type="warning" plain @click="$router.push(`/goods/edit/${row.barcode}`)">编辑</el-button>
            <el-popconfirm title="确定删除？" @confirm="handleDelete(row.barcode)">
              <template #reference>
                <el-button size="small" type="danger" plain>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const category = ref('')
const loading = ref(false)

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/goods', {
      params: { page: page.value, page_size: pageSize.value, keyword: keyword.value, category: category.value },
    })
    list.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function handleDelete(barcode) {
  try {
    await api.delete(`/goods/${barcode}`)
    ElMessage.success('删除成功')
    loadData()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function imgUrl(path) {
  if (!path) return ''
  return path.startsWith('http') ? path : `/api/file/${path}`
}

onMounted(loadData)
</script>

<style scoped>
.goods-list { padding: 20px; }
.list-card { border-radius: 12px; }
.toolbar { display: flex; align-items: center; }
.goods-thumb {
  border-radius: 8px;
  border: 2px solid #f0e6dc;
}
.price-text {
  color: #e8733a;
  font-weight: 700;
  font-size: 15px;
}
:deep(.table-row:hover > td) {
  background: #faf2ec !important;
}
</style>
