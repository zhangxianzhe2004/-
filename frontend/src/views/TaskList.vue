<template>
  <div class="task-list">
    <el-card class="task-card">
      <div class="toolbar">
        <el-select v-model="filterStatus" placeholder="状态筛选" clearable style="width: 160px" @change="loadData">
          <el-option label="待处理" value="pending" />
          <el-option label="处理中" value="processing" />
          <el-option label="成功" value="success" />
          <el-option label="部分成功" value="partial" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button @click="loadData" type="primary" plain style="margin-left: 10px">
          <el-icon style="margin-right:4px"><Refresh /></el-icon>刷新
        </el-button>
      </div>
      <el-table :data="list" v-loading="loading" style="margin-top: 16px" row-class-name="table-row">
        <el-table-column prop="task_id" label="任务ID" width="280" show-overflow-tooltip />
        <el-table-column prop="task_name" label="任务名称" min-width="160" />
        <el-table-column prop="source" label="来源" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" effect="light">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <span class="progress-text">{{ row.success_count }}/{{ row.total_count }}</span>
            <el-progress
              :percentage="row.total_count ? Math.round((row.success_count / row.total_count) * 100) : 0"
              :status="row.status === 'failed' ? 'exception' : row.status === 'success' ? 'success' : ''"
            />
          </template>
        </el-table-column>
        <el-table-column prop="fail_count" label="失败数" width="80" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column prop="finished_at" label="完成时间" width="180" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" type="warning" plain @click="downloadReport(row.task_id)">
              <el-icon style="margin-right:4px"><Download /></el-icon>下载报告
            </el-button>
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
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterStatus = ref('')
const loading = ref(false)
let timer = null

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/import/tasks', {
      params: { page: page.value, page_size: pageSize.value, status: filterStatus.value || undefined },
    })
    list.value = res.items
    total.value = res.total
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function downloadReport(taskId) {
  window.open(`/api/import/tasks/${taskId}/report`, '_blank')
}

function statusType(s) {
  const map = { pending: 'info', processing: 'warning', success: 'success', partial: 'warning', failed: 'danger' }
  return map[s] || 'info'
}
function statusLabel(s) {
  const map = { pending: '待处理', processing: '处理中', success: '成功', partial: '部分成功', failed: '失败' }
  return map[s] || s
}

// 自动刷新（处理中的任务进度更新）
onMounted(() => {
  loadData()
  timer = setInterval(() => {
    if (list.value.some((t) => t.status === 'pending' || t.status === 'processing')) {
      loadData()
    }
  }, 5000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.task-list { padding: 20px; }
.task-card { border-radius: 12px; }
.toolbar { display: flex; align-items: center; }
.progress-text {
  font-size: 13px;
  color: #8a7a6a;
}
:deep(.table-row:hover > td) {
  background: #faf2ec !important;
}
</style>
