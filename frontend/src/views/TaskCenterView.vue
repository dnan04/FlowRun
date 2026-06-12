<template>
  <section>
    <div class="task-center-layout">
      <DirectoryTreePanel
        v-model="selectedDirectoryId"
        :directories="directories"
        :tasks="tasks"
        :can-manage="auth.isAdmin"
        :deleting-directory-id="deletingDirectoryId"
        @create="openCreateDirectory"
        @rename="renameDirectory"
        @delete="deleteDirectory"
      />

      <div class="task-center-content">
        <div class="task-toolbar">
          <div class="task-toolbar-title">
            <strong>{{ selectedDirectoryName }}</strong>
            <span>{{ filteredTasks.length }} 个任务</span>
          </div>
          <div class="task-toolbar-actions">
            <el-button v-if="auth.isAdmin" type="primary" @click="openTaskPicker">
              <el-icon><Plus /></el-icon>
              添加任务
            </el-button>
            <el-button @click="loadAll">
              <el-icon><Refresh /></el-icon>
              刷新任务
            </el-button>
          </div>
        </div>

        <el-empty v-if="filteredTasks.length === 0" class="task-empty" description="当前目录暂无任务" />

        <div v-else class="task-grid">
          <el-card v-for="task in filteredTasks" :key="task.id" class="glass-card task-card">
            <template #header>
              <div class="task-header">
                <div class="task-title">{{ task.display_name }}</div>
                <div class="task-card-tools">
                  <el-button
                    text
                    type="primary"
                    size="small"
                    :loading="loadingLogTaskId === task.id"
                    @click.stop="openTaskLogs(task)"
                  >
                    日志
                  </el-button>
                  <el-tag>{{ task.engineType }}</el-tag>
                  <el-button
                    v-if="auth.isAdmin"
                    text
                    type="danger"
                    size="small"
                    :loading="removingTaskId === task.id"
                    @click.stop="removeTaskFromCenter(task)"
                  >
                    移除
                  </el-button>
                </div>
              </div>
            </template>

            <div class="task-meta-list">
              <div class="meta-block">
                <strong>执行前提</strong>
                <span class="meta-value meta-clamp-3" :title="formatText(task.prerequisite)">
                  {{ formatText(task.prerequisite) }}
                </span>
              </div>
              <div class="meta-block">
                <strong>影响范围</strong>
                <span class="meta-value meta-clamp-3" :title="formatText(task.impactScope)">
                  {{ formatText(task.impactScope) }}
                </span>
              </div>
              <div class="meta-block">
                <strong>可执行人员</strong>
                <span class="meta-value meta-clamp-2" :title="formatUsers(task.executableUserNames)">
                  {{ formatUsers(task.executableUserNames) }}
                </span>
              </div>
              <div class="meta-block">
                <strong>失败联系人</strong>
                <span class="meta-value meta-clamp-2" :title="formatFailureContact(task.failureContact)">
                  {{ formatFailureContact(task.failureContact) }}
                </span>
              </div>
            </div>

            <div class="task-actions">
              <el-button
                type="primary"
                :disabled="!canExecuteTask(task)"
                :loading="runningId === task.id"
                :title="getExecuteDisabledReason(task)"
                @click="runTask(task)"
              >
                执行任务
              </el-button>
            </div>
          </el-card>
        </div>
      </div>
    </div>

    <el-dialog v-model="taskPickerVisible" title="添加任务到任务中心" width="760px">
      <div class="task-picker-toolbar">
        <el-input
          v-model="taskPickerKeyword"
          clearable
          placeholder="搜索任务名称"
        />
      </div>
      <el-table :data="filteredConfiguredTasks" v-loading="loadingConfiguredTasks">
        <el-table-column prop="taskCode" label="编码" width="70" />
        <el-table-column label="目录" width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ formatDirectoryName(row.directoryPath || row.directoryName) }}</template>
        </el-table-column>
        <el-table-column prop="displayName" label="任务名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="engineType" label="方式" width="100" />
        <el-table-column label="发布" width="90">
          <template #default="{ row }">
            <el-tag :type="row.published ? 'success' : 'info'">
              {{ row.published ? '已发布' : '未发布' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button
              text
              type="primary"
              :disabled="isTaskInCenter(row.id) || !row.published"
              :loading="publishingTaskId === row.id"
              @click="addConfiguredTask(row)"
            >
              添加
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="logDialogVisible" :title="`${selectedTaskName || ''} 执行日志`" width="1080px">
      <el-table :data="taskLogs" v-loading="loadingLogTaskId !== null">
        <el-table-column label="执行时间" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.started_at || row.requested_at) }}</template>
        </el-table-column>
        <el-table-column label="完成时间" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.finished_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <StatusTag :status="row.execution_status" />
          </template>
        </el-table-column>
        <el-table-column prop="requested_by_name" label="执行人" width="120" />
        <el-table-column label="日志信息" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.error_summary || row.result_summary || '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="executionResultVisible" :title="`${executionResultTaskName || ''} 执行结果`" width="560px">
      <div v-if="executionResult" class="execution-result-panel">
        <div class="execution-result-header">
          <span>执行状态</span>
          <StatusTag :status="executionResult.execution_status" />
        </div>
        <div class="execution-result-meta">
          <span>提交时间</span>
          <strong>{{ formatDateTime(executionResult.requested_at) }}</strong>
          <span>完成时间</span>
          <strong>{{ formatDateTime(executionResult.finished_at) }}</strong>
        </div>
        <div class="execution-result-message">
          {{ executionResult.error_summary || executionResult.result_summary || (resultPolling ? '任务正在执行，请稍候...' : '-') }}
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="directoryDialogVisible" title="创建目录" width="420px">
      <el-form label-position="top">
        <el-form-item label="父级目录">
          <el-input :model-value="newDirectoryParentName" disabled />
        </el-form-item>
        <el-form-item label="目录名称">
          <el-input v-model="newDirectoryName" placeholder="例如 财务亚洲、供应链发货" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="directoryDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingDirectory" @click="createDirectory">创建</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import http from '../api/http'
import DirectoryTreePanel from '../components/DirectoryTreePanel.vue'
import StatusTag from '../components/StatusTag.vue'
import { useAuthStore } from '../stores/auth'

const tasks = ref<any[]>([])
const directories = ref<any[]>([])
const configuredTasks = ref<any[]>([])
const runningId = ref<number | null>(null)
const publishingTaskId = ref<number | null>(null)
const removingTaskId = ref<number | null>(null)
const loadingLogTaskId = ref<number | null>(null)
const taskPickerVisible = ref(false)
const taskPickerKeyword = ref('')
const loadingConfiguredTasks = ref(false)
const logDialogVisible = ref(false)
const executionResultVisible = ref(false)
const executionResult = ref<any | null>(null)
const executionResultTaskName = ref('')
const resultPolling = ref(false)
const directoryDialogVisible = ref(false)
const creatingDirectory = ref(false)
const deletingDirectoryId = ref<number | null>(null)
const newDirectoryName = ref('')
const newDirectoryParentId = ref<number | null>(null)
const selectedDirectoryId = ref<number | 'all' | null>('all')
const selectedTaskName = ref('')
const taskLogs = ref<any[]>([])
const auth = useAuthStore()
const DEFAULT_LOG_LIMIT = 10

const filteredTasks = computed(() => {
  if (selectedDirectoryId.value === 'all') {
    return tasks.value
  }
  if (selectedDirectoryId.value === null) {
    return tasks.value.filter((task) => (task.directoryId ?? null) === null)
  }
  const directoryIds = collectDirectoryIds(selectedDirectoryId.value)
  return tasks.value.filter((task) => directoryIds.includes(task.directoryId))
})

const selectedDirectoryName = computed(() => {
  if (selectedDirectoryId.value === 'all') {
    return '全部任务'
  }
  if (selectedDirectoryId.value === null) {
    return '未分类'
  }
  const directory = directories.value.find((item) => item.id === selectedDirectoryId.value)
  return directory?.directoryPath || directory?.directoryName || '当前目录'
})

const filteredConfiguredTasks = computed(() => {
  const keyword = taskPickerKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return configuredTasks.value
  }
  return configuredTasks.value.filter((task) => {
    return `${task.displayName || ''}`.toLowerCase().includes(keyword)
  })
})

const newDirectoryParentName = computed(() => {
  if (newDirectoryParentId.value === null) {
    return '全部'
  }
  return directories.value.find((directory) => directory.id === newDirectoryParentId.value)?.directoryName || '全部'
})

const loadTasks = async () => {
  const { data } = await http.get('/tasks/my')
  tasks.value = data
}

const loadDirectories = async () => {
  const { data } = await http.get('/tasks/directories')
  directories.value = data
}

const loadAll = async () => {
  await Promise.all([loadTasks(), loadDirectories()])
}

const formatUsers = (names?: string[]) => {
  return names?.length ? names.join('、') : '-'
}

const formatText = (value?: string | null) => {
  return value?.trim() || '-'
}

const formatFailureContact = (value?: string | null) => {
  const text = value?.trim()
  if (!text) {
    return '-'
  }
  return text
    .replace(/[（(][^（）()]*@[^（）()]*[）)]/g, '')
    .split('、')
    .map((item) => item.trim())
    .filter(Boolean)
    .join('、') || '-'
}

const formatDirectoryName = (value?: string | null) => {
  return value?.trim() || '未分类'
}

const collectDirectoryIds = (directoryId: number) => {
  const ids = [directoryId]
  const appendChildren = (parentId: number) => {
    directories.value
      .filter((directory) => directory.parentDirectoryId === parentId)
      .forEach((directory) => {
        ids.push(directory.id)
        appendChildren(directory.id)
      })
  }
  appendChildren(directoryId)
  return ids
}

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`
  const date = new Date(normalized)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).format(date)
}

const isTaskInCenter = (taskId: number) => {
  return tasks.value.some((task) => task.id === taskId)
}

const canExecuteTask = (task: any) => {
  return auth.isAdmin || task.canExecute === true
}

const getExecuteDisabledReason = (task: any) => {
  if (canExecuteTask(task)) {
    return ''
  }
  if (isCurrentUserExecutable(task) && task.executionWindowCron) {
    return `当前任务不在允许执行时间内（Cron: ${task.executionWindowCron}）`
  }
  return '当前用户仅可查看，无法执行'
}

const isCurrentUserExecutable = (task: any) => {
  const email = auth.user?.email || auth.user?.username
  return Boolean(email && task.executableUserEmails?.includes(email))
}

const loadConfiguredTasks = async () => {
  if (!auth.isAdmin) {
    return
  }
  loadingConfiguredTasks.value = true
  try {
    const { data } = await http.get('/admin/tasks')
    configuredTasks.value = data
  } finally {
    loadingConfiguredTasks.value = false
  }
}

const openTaskPicker = async () => {
  taskPickerVisible.value = true
  taskPickerKeyword.value = ''
  await loadConfiguredTasks()
}

const openCreateDirectory = (parentId: number | null) => {
  newDirectoryParentId.value = parentId
  newDirectoryName.value = ''
  directoryDialogVisible.value = true
}

const createDirectory = async () => {
  const name = newDirectoryName.value.trim()
  if (!name) {
    ElMessage.error('目录名称不能为空')
    return
  }
  try {
    creatingDirectory.value = true
    const { data } = await http.post('/admin/task-directories', {
      directoryName: name,
      parentDirectoryId: newDirectoryParentId.value
    })
    ElMessage.success('目录已创建')
    newDirectoryName.value = ''
    newDirectoryParentId.value = null
    directoryDialogVisible.value = false
    await loadDirectories()
    selectedDirectoryId.value = data.id
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建目录失败')
  } finally {
    creatingDirectory.value = false
  }
}

const renameDirectory = async (directory: any) => {
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入新的目录名称',
      '重命名目录',
      {
        inputValue: directory.directoryName,
        inputPattern: /\S+/,
        inputErrorMessage: '目录名称不能为空',
        confirmButtonText: '保存',
        cancelButtonText: '取消'
      }
    )
    const name = `${value}`.trim()
    if (!name) {
      ElMessage.error('目录名称不能为空')
      return
    }
    await http.put(`/admin/task-directories/${directory.id}`, {
      directoryName: name
    })
    ElMessage.success('目录已重命名')
    await loadAll()
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.detail || '重命名目录失败')
  }
}

const deleteDirectory = async (directory: any) => {
  try {
    const deletedDirectoryIds = collectDirectoryIds(directory.id)
    await ElMessageBox.confirm(
      `删除目录“${directory.directoryName}”吗？目录下任务会调整为未分类。`,
      '删除目录',
      { type: 'warning' }
    )
    deletingDirectoryId.value = directory.id
    await http.delete(`/admin/task-directories/${directory.id}`)
    ElMessage.success('目录已删除')
    if (typeof selectedDirectoryId.value === 'number' && deletedDirectoryIds.includes(selectedDirectoryId.value)) {
      selectedDirectoryId.value = 'all'
    }
    await loadAll()
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.detail || '删除目录失败')
  } finally {
    deletingDirectoryId.value = null
  }
}

const addConfiguredTask = async (row: any) => {
  try {
    publishingTaskId.value = row.id
    await http.post(`/admin/tasks/${row.id}/add-to-center`)
    ElMessage.success('任务已添加到任务中心')
    await Promise.all([loadConfiguredTasks(), loadTasks()])
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '添加任务失败')
  } finally {
    publishingTaskId.value = null
  }
}

const removeTaskFromCenter = async (task: any) => {
  try {
    await ElMessageBox.confirm(
      `将“${task.display_name}”从任务中心移除吗？`,
      '移除任务',
      { type: 'warning' }
    )
    removingTaskId.value = task.id
    await http.post(`/admin/tasks/${task.id}/remove-from-center`)
    ElMessage.success('任务已从任务中心移除')
    await Promise.all([loadTasks(), taskPickerVisible.value ? loadConfiguredTasks() : Promise.resolve()])
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.detail || '移除任务失败')
  } finally {
    removingTaskId.value = null
  }
}

const openTaskLogs = async (task: any) => {
  try {
    selectedTaskName.value = task.display_name
    logDialogVisible.value = true
    loadingLogTaskId.value = task.id
    taskLogs.value = []
    const { data } = await http.get(`/tasks/${task.id}/executions`)
    taskLogs.value = data.slice(0, DEFAULT_LOG_LIMIT)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '获取执行日志失败')
  } finally {
    loadingLogTaskId.value = null
  }
}

const runTask = async (task: any) => {
  if (!canExecuteTask(task)) {
    ElMessage.warning(getExecuteDisabledReason(task))
    return
  }
  const taskId = task.id
  try {
    runningId.value = taskId
    executionResultTaskName.value = task.display_name || ''
    executionResultVisible.value = true
    resultPolling.value = true
    const { data } = await http.post(`/tasks/${taskId}/execute`, {})
    executionResult.value = data
    ElMessage.success('任务已提交，平台正在执行')
    await waitForExecutionResult(taskId, data.id)
    await loadAll()
  } catch (error: any) {
    resultPolling.value = false
    ElMessage.error(error?.response?.data?.detail || '执行失败')
  } finally {
    runningId.value = null
  }
}

const waitForExecutionResult = async (taskId: number, executionId: number) => {
  const terminalStatuses = new Set(['SUCCEEDED', 'FAILED', 'CANCELED'])
  for (let index = 0; index < 60; index += 1) {
    await sleep(1000)
    const { data } = await http.get(`/tasks/${taskId}/executions`)
    const latest = data.find((item: any) => item.id === executionId)
    if (latest) {
      executionResult.value = latest
      if (terminalStatuses.has(latest.execution_status)) {
        resultPolling.value = false
        latest.execution_status === 'SUCCEEDED'
          ? ElMessage.success('任务执行成功')
          : ElMessage.error(latest.error_summary || '任务执行失败')
        return
      }
    }
  }
  resultPolling.value = false
}

const sleep = (duration: number) => new Promise((resolve) => window.setTimeout(resolve, duration))

onMounted(loadAll)
</script>

<style scoped>
.task-header,
.task-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.task-header {
  gap: 6px;
  min-width: 0;
}

.task-center-content {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.task-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 52px;
  padding: 10px 12px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 6px 18px rgba(31, 45, 61, 0.05);
}

.task-toolbar-title {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.task-toolbar-title strong {
  min-width: 0;
  color: #1f2d3d;
  font-size: 16px;
  line-height: 22px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-toolbar-title span {
  color: var(--muted);
  font-size: 13px;
}

.task-toolbar-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 10px;
  align-items: center;
}

.task-center-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.task-card {
  display: flex;
  flex-direction: column;
  height: 310px;
  border-radius: 8px;
  overflow: hidden;
  transition:
    box-shadow 0.16s ease,
    transform 0.16s ease,
    border-color 0.16s ease;
}

.task-card:hover {
  border-color: rgba(62, 111, 244, 0.24);
  box-shadow: 0 12px 28px rgba(31, 45, 61, 0.1);
  transform: translateY(-1px);
}

.task-card :deep(.el-card__header) {
  flex: 0 0 auto;
  padding: 10px 12px;
}

.task-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 10px;
  overflow: hidden;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.task-picker-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.task-picker-toolbar :deep(.el-input) {
  max-width: 280px;
}

.task-empty {
  min-height: 280px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #fff;
}

.task-title {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 16px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-card-tools {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 3px;
  white-space: nowrap;
}

.task-card-tools :deep(.el-button.is-text) {
  min-height: 22px;
  padding: 0 3px;
  font-size: 12px;
}

.task-card-tools :deep(.el-tag) {
  height: 20px;
  padding: 0 5px;
  font-size: 12px;
  line-height: 18px;
}

.task-meta-list {
  flex: 0 0 196px;
  overflow: hidden;
}

.meta-block {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: 5px;
  margin-bottom: 3px;
  font-size: 13px;
  line-height: 17px;
}

.meta-value {
  min-width: 0;
  overflow: hidden;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-box-orient: vertical;
}

.meta-clamp-1 {
  display: block;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-clamp-2 {
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.meta-clamp-3 {
  -webkit-line-clamp: 3;
  line-clamp: 3;
}

.task-actions {
  gap: 8px;
  justify-content: space-between;
  margin-top: 14px;
  padding-top: 0;
}

.task-actions :deep(.el-button) {
  min-height: 28px;
  min-width: 82px;
  padding-left: 10px;
  padding-right: 10px;
}

.execution-result-panel {
  display: grid;
  gap: 14px;
}

.execution-result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 700;
}

.execution-result-meta {
  display: grid;
  grid-template-columns: 80px minmax(0, 1fr);
  gap: 8px 12px;
  color: var(--muted);
}

.execution-result-meta strong {
  min-width: 0;
  color: var(--text);
  overflow-wrap: anywhere;
}

.execution-result-message {
  min-height: 96px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  color: #344056;
  line-height: 1.7;
  white-space: pre-wrap;
  background: #f7f9fc;
}

@media (max-width: 1320px) {
  .task-grid {
    grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  }
}

@media (max-width: 1020px) {
  .task-center-layout {
    grid-template-columns: 1fr;
  }

  .directory-panel {
    position: static;
    grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
  }

  .directory-header {
    grid-column: 1 / -1;
  }

  .task-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .task-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .task-toolbar-actions {
    justify-content: flex-end;
  }

  .task-grid {
    grid-template-columns: 1fr;
  }
}
</style>
