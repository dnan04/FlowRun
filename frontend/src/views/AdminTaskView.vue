<template>
  <section class="admin-grid">
    <DirectoryTreePanel
      v-model="selectedDirectoryId"
      :directories="directories"
      :tasks="tasks"
      can-manage
      :deleting-directory-id="deletingDirectoryId"
      @create="openCreateDirectory"
      @rename="renameDirectory"
      @delete="deleteDirectory"
    />


    <el-card class="glass-card task-config-card">
      <template #header>
        <div class="task-config-title">
          <div class="section-title">任务配置</div>
          <el-tooltip
            content="管理员在这里维护任务按钮、执行方式、参数模板和授权范围。任务先执行测试，确认成功后再发布到任务中心。"
            placement="top"
          >
            <span class="help-icon">i</span>
          </el-tooltip>
        </div>
      </template>

      <el-form label-position="top">
        <el-row :gutter="14">
          <el-col :xl="4" :lg="4" :md="6" :sm="24" :xs="24">
            <el-form-item>
              <template #label>
                <span class="label-with-help">
                  <span><span class="required-mark">*</span>任务编码</span>
                  <el-tooltip content="系统自动分配，删除任务后会自动重新编号。" placement="top">
                    <span class="help-icon">i</span>
                  </el-tooltip>
                </span>
              </template>
              <el-input v-model="form.taskCode" readonly disabled />
            </el-form-item>
          </el-col>
          <el-col :xl="7" :lg="7" :md="18" :sm="24" :xs="24">
            <el-form-item>
              <template #label><span><span class="required-mark">*</span>任务名称</span></template>
              <el-input v-model="form.displayName" placeholder="例如 财务成本明细重算" />
            </el-form-item>
          </el-col>
          <el-col :xl="5" :lg="5" :md="12" :sm="24" :xs="24">
            <el-form-item>
              <template #label>
                <span class="label-with-help">
                  <span>重复触发窗口</span>
                  <el-tooltip content="单位为分钟。同一任务在窗口期内若存在 PENDING/RUNNING 记录，会拦截重复触发；留空表示不限制。" placement="top">
                    <span class="help-icon">i</span>
                  </el-tooltip>
                </span>
              </template>
              <el-input-number
                v-model="form.repeatWindowMinutes"
                :min="1"
                :max="240"
                :value-on-clear="undefined"
                placeholder="默认空"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xl="8" :lg="8" :md="12" :sm="24" :xs="24">
            <el-form-item>
              <template #label>
                <span class="label-with-help">
                  <span>用户允许执行时间</span>
                  <el-tooltip content="使用 5 段 Cron 表达式：分钟 小时 日 月 星期。例如 * * 1-10 * * 表示每月 1-10 号允许执行；留空表示不限制。" placement="top">
                    <span class="help-icon">i</span>
                  </el-tooltip>
                </span>
              </template>
              <el-input
                v-model="form.executionWindowCron"
                clearable
                placeholder="例如 * * 1-10 * *"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item>
              <template #label><span>影响范围</span></template>
              <el-input v-model="form.impactScope" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item>
              <template #label><span>执行前提</span></template>
              <el-input v-model="form.prerequisite" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="所属目录">
              <el-select v-model="form.directoryId" clearable filterable style="width: 100%" placeholder="默认未分类">
                <el-option
                  v-for="directory in directorySelectOptions"
                  :key="directory.id"
                  :label="directory.optionLabel"
                  :value="directory.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item>
              <template #label><span><span class="required-mark">*</span>执行方式</span></template>
              <el-select v-model="form.engineType" style="width: 100%">
                <el-option label="DS 工作流" value="DS" />
                <el-option label="PG 存储过程" value="PG" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <template v-if="isDsTask">
          <div class="subsection-heading">
            <div class="subsection-title label-with-help">
              <span>DS 启动流程实例参数</span>
              <el-tooltip
                content="下列字段用于配置 `POST /dolphinscheduler/projects/{projectCode}/executors/start-process-instance` 的调用参数。"
                placement="top"
              >
                <span class="help-icon">i</span>
              </el-tooltip>
            </div>
          </div>

          <el-row :gutter="14">
            <el-col :span="12">
              <el-form-item>
                <template #label><span><span class="required-mark">*</span>流程定义编码</span></template>
                <el-input v-model="form.engineTarget" placeholder="对应 processDefinitionCode" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item>
                <template #label><span><span class="required-mark">*</span>项目名称(projectCode)</span></template>
                <el-select v-model="form.dsProjectCode" filterable placeholder="请选择项目" style="width: 100%">
                  <el-option
                    v-for="option in dsOptions.projects"
                    :key="option.code"
                    :label="formatProjectOption(option)"
                    :value="option.code"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="14">
            <el-col :span="12">
              <el-form-item>
                <template #label><span><span class="required-mark">*</span>失败策略(failureStrategy)</span></template>
                <el-select v-model="form.dsFailureStrategy" style="width: 100%">
                  <el-option label="CONTINUE" value="CONTINUE" />
                  <el-option label="END" value="END" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item>
                <template #label><span><span class="required-mark">*</span>流程优先级(processInstancePriority)</span></template>
                <el-select v-model="form.dsProcessInstancePriority" style="width: 100%">
                  <el-option label="HIGHEST" value="HIGHEST" />
                  <el-option label="HIGH" value="HIGH" />
                  <el-option label="MEDIUM" value="MEDIUM" />
                  <el-option label="LOW" value="LOW" />
                  <el-option label="LOWEST" value="LOWEST" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item>
                <template #label><span><span class="required-mark">*</span>通知策略(warningType)</span></template>
                <el-select v-model="form.dsWarningType" style="width: 100%">
                  <el-option label="NONE" value="NONE" />
                  <el-option label="SUCCESS" value="SUCCESS" />
                  <el-option label="FAILURE" value="FAILURE" />
                  <el-option label="ALL" value="ALL" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item>
                <template #label><span><span class="required-mark">*</span>Worker分组(workerGroup)</span></template>
                <el-input v-model="form.dsWorkerGroup" disabled />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="14">
            <el-col :span="12">
              <el-form-item>
                <template #label><span><span class="required-mark">*</span>执行类型(execType)</span></template>
                <el-input v-model="form.dsExecType" disabled />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item>
                <template #label><span>启动参数(startParams(JSON))</span></template>
                <el-input v-model="dsStartParamsText" type="textarea" :rows="2" :placeholder="DS_START_PARAMS_PLACEHOLDER" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="14">
            <el-col :span="12">
              <el-form-item label="环境名称(environmentCode)">
                <el-select
                  v-model="form.dsEnvironmentCode"
                  clearable
                  filterable
                  placeholder="默认空"
                  style="width: 100%"
                >
                  <el-option
                    v-for="option in dsOptions.environments"
                    :key="option.code"
                    :label="formatEnvironmentOption(option)"
                    :value="option.code"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="告警组(warningGroup)">
                <el-select
                  v-model="form.dsWarningGroupId"
                  clearable
                  filterable
                  placeholder="默认空"
                  style="width: 100%"
                >
                  <el-option
                    v-for="option in dsOptions.warningGroups"
                    :key="option.id"
                    :label="formatWarningGroupOption(option)"
                    :value="`${option.id}`"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item>
            <template #label>
              <span class="label-with-help">
                <span>后置方法</span>
                <el-tooltip content="可不填。填写时在 DS 任务成功后调用，必须使用 :job_instance_name 占位符。" placement="top">
                  <span class="help-icon">i</span>
                </el-tooltip>
              </span>
            </template>
            <el-input
              v-model="form.dsCallbackMethod"
              type="textarea"
              :rows="3"
              placeholder="例如 SELECT * FROM public.after_ds(:job_instance_name);"
            />
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item>
            <template #label>
              <span class="label-with-help">
                <span>存储过程</span>
                <el-tooltip content="必须使用:job_instance_name占位符。" placement="top">
                  <span class="help-icon">i</span>
                </el-tooltip>
              </span>
            </template>
            <el-input
              v-model="pgParameterText"
              type="textarea"
              :rows="4"
              placeholder="例如 call public.p_a(:job_instance_name); call public.p_b()"
            />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="label-with-help">
                <span>后置方法</span>
                <el-tooltip content="可不填。填写时在 PG 存储过程执行后调用，必须使用 :job_instance_name 占位符。" placement="top">
                  <span class="help-icon">i</span>
                </el-tooltip>
              </span>
            </template>
            <el-input
              v-model="form.pgCallbackMethod"
              type="textarea"
              :rows="3"
              placeholder="例如 SELECT * FROM public.get_user_rank(:job_instance_name) ;"
            />
          </el-form-item>
        </template>

        <el-form-item label="失败联系人">
          <el-select
            v-model="form.notifyUserEmails"
            multiple
            filterable
            remote
            :remote-method="searchUsers"
            :loading="loadingUsers"
            :reserve-keyword="false"
            style="width: 100%"
            @focus="loadDefaultUsers"
          >
            <el-option
              v-for="item in users"
              :key="item.email"
              :label="formatUserOption(item)"
              :value="item.email"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="可见人员">
          <el-select
            v-model="form.visibleUserEmails"
            multiple
            filterable
            remote
            :remote-method="searchUsers"
            :loading="loadingUsers"
            :reserve-keyword="false"
            style="width: 100%"
            @focus="loadDefaultUsers"
          >
            <el-option
              v-for="item in users"
              :key="item.email"
              :label="formatUserOption(item)"
              :value="item.email"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="可执行人员">
          <el-select
            v-model="form.executableUserEmails"
            multiple
            filterable
            remote
            :remote-method="searchUsers"
            :loading="loadingUsers"
            :reserve-keyword="false"
            style="width: 100%"
            @focus="loadDefaultUsers"
          >
            <el-option
              v-for="item in users"
              :key="item.email"
              :label="formatUserOption(item)"
              :value="item.email"
            />
          </el-select>
        </el-form-item>
        <div class="action-row">
          <el-button @click="resetForm">重置</el-button>
          <el-button type="primary" :loading="saving" @click="saveTask">保存配置</el-button>
          <el-button type="success" :loading="testing" @click="testTask">执行测试</el-button>
          <el-button type="warning" :disabled="publishDisabled" :loading="publishing" @click="publishTask">
            发布任务
          </el-button>
        </div>
      </el-form>

      <div v-if="testResult" class="test-result" :class="testResult.success ? 'is-success' : 'is-failed'">
        <div class="result-header">
          <span class="subsection-title">最近一次测试结果</span>
          <el-tag :type="testResult.success ? 'success' : 'danger'">
            {{ testResult.success ? 'SUCCESS' : 'FAILED' }}
          </el-tag>
        </div>
        <div class="result-message">{{ testResult.message }}</div>
        <div class="result-grid" v-if="testResult.workflowSummary">
          <div class="result-item">
            <span class="meta-text">流程实例 ID</span>
            <strong>{{ testResult.workflowSummary.processInstanceId || '-' }}</strong>
          </div>
          <div class="result-item">
            <span class="meta-text">实例状态</span>
            <strong>{{ testResult.workflowSummary.processInstanceState || '-' }}</strong>
          </div>
          <div class="result-item">
            <span class="meta-text">实例名称</span>
            <strong>{{ testResult.workflowSummary.processInstanceName || '-' }}</strong>
          </div>
          <div class="result-item">
            <span class="meta-text">执行用户</span>
            <strong>{{ testResult.workflowSummary.executorName || '-' }}</strong>
          </div>
        </div>
      </div>
    </el-card>

    <el-card class="glass-card configured-tasks-card">
      <template #header>
        <div class="table-card-header">
          <div class="section-title">已配置任务</div>
          <el-button type="primary" @click="resetForm">新增任务</el-button>
        </div>
      </template>
      <div class="configured-task-layout">
        <div class="task-list-toolbar">
          <el-input
            v-model="taskKeyword"
            clearable
            placeholder="搜索任务名称/编码"
            @keyup.enter="searchTasks"
            @clear="searchTasks"
          />
          <el-select v-model="taskEngineType" clearable placeholder="执行方式" @change="searchTasks">
            <el-option label="DS 工作流" value="DS" />
            <el-option label="PG 存储过程" value="PG" />
          </el-select>
          <el-button type="primary" @click="searchTasks">搜索</el-button>
        </div>
        <el-table :data="filteredTasks" class="task-table" table-layout="fixed" v-loading="loadingTasks">
          <el-table-column prop="taskCode" label="编码" width="42" />
          <el-table-column label="目录" width="94" show-overflow-tooltip>
            <template #default="{ row }">{{ formatDirectoryName(row.directoryPath || row.directoryName) }}</template>
          </el-table-column>
          <el-table-column prop="displayName" label="任务名称" min-width="80" show-overflow-tooltip />
          <el-table-column prop="engineType" label="方式" width="44" />
          <el-table-column label="测试" width="62">
            <template #default="{ row }">
              <el-tag :type="row.lastTestSuccess ? 'success' : row.lastTestSuccess === false ? 'danger' : 'info'">
                {{ row.lastTestSuccess === true ? '已通过' : row.lastTestSuccess === false ? '未通过' : '未测试' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="发布" width="58">
            <template #default="{ row }">
              <el-tag :type="row.published ? 'success' : 'info'">
                {{ row.published ? '已发布' : '未发布' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="76">
            <template #default="{ row }">
              <div class="table-actions">
                <el-button text @click="editTask(row)">编辑</el-button>
                <el-button text type="danger" @click="removeTask(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="taskPage"
          v-model:page-size="taskPageSize"
          class="task-pagination"
          layout="total, sizes, prev, pager, next"
          :page-sizes="[10, 20, 50, 100]"
          :total="taskTotal"
          @current-change="loadTasks"
          @size-change="handleTaskPageSizeChange"
        />
      </div>
    </el-card>

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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api/http'
import DirectoryTreePanel from '../components/DirectoryTreePanel.vue'

type TaskRow = Record<string, any>

const DEFAULT_PG_TEMPLATE = ''
const DEFAULT_DS_START_PARAMS = ''
const DS_START_PARAMS_PLACEHOLDER = '默认空。填写 JSON 对象，例如 {"businessDate":"2026-05-07","region":"asia"}'
const LONG_RUNNING_REQUEST_CONFIG = { timeout: 0 }

const users = ref<any[]>([])
const tasks = ref<TaskRow[]>([])
const loadingTasks = ref(false)
const taskTotal = ref(0)
const taskPage = ref(1)
const taskPageSize = ref(20)
const taskKeyword = ref('')
const taskEngineType = ref('')
const directories = ref<any[]>([])
const selectedDirectoryId = ref<number | 'all' | null>('all')
const directoryDialogVisible = ref(false)
const creatingDirectory = ref(false)
const deletingDirectoryId = ref<number | null>(null)
const loadingUsers = ref(false)
const newDirectoryName = ref('')
const newDirectoryParentId = ref<number | null>(null)
const saving = ref(false)
const testing = ref(false)
const publishing = ref(false)
const testResult = ref<any | null>(null)
const lastTestPassed = ref(false)
const testedDraftSignature = ref('')
const pgParameterText = ref(DEFAULT_PG_TEMPLATE)
const dsStartParamsText = ref(DEFAULT_DS_START_PARAMS)
const dsDefaults = reactive({
  defaultProjectCode: '',
  workerGroup: 'default',
  failureStrategy: 'CONTINUE',
  processInstancePriority: 'MEDIUM',
  warningType: 'NONE',
  execType: 'START_PROCESS',
  defaultEnvironmentCode: '',
  defaultWarningGroupId: '',
  defaultDsCallbackMethod: '',
  defaultPgCallbackMethod: ''
})
const dsOptions = reactive({
  projects: [] as any[],
  environments: [] as any[],
  warningGroups: [] as any[]
})

const createInitialForm = () => ({
  id: undefined as number | undefined,
  directoryId: null as number | null,
  taskCode: '1',
  displayName: '',
  description: null as string | null,
  scenario: '',
  prerequisite: '',
  impactScope: '',
  failureContact: '',
  engineType: 'DS',
  engineTarget: '',
  dsCallbackMethod: dsDefaults.defaultDsCallbackMethod,
  pgCallbackMethod: dsDefaults.defaultPgCallbackMethod,
  repeatWindowMinutes: undefined as number | undefined,
  executionWindowCron: '',
  visibleUserEmails: [] as string[],
  executableUserEmails: [] as string[],
  notifyUserEmails: [] as string[],
  published: false,
  dsProjectCode: '',
  dsFailureStrategy: dsDefaults.failureStrategy,
  dsProcessInstancePriority: dsDefaults.processInstancePriority,
  dsWarningType: dsDefaults.warningType,
  dsWorkerGroup: dsDefaults.workerGroup,
  dsExecType: dsDefaults.execType,
  dsEnvironmentCode: dsDefaults.defaultEnvironmentCode,
  dsWarningGroupId: dsDefaults.defaultWarningGroupId
})

const form = reactive(createInitialForm())
const isDsTask = computed(() => form.engineType === 'DS')

const filteredTasks = computed(() => {
  return tasks.value
})

const directorySelectOptions = computed(() => directories.value.map((directory) => ({
  ...directory,
  optionLabel: `${directory.level === 3 ? '  ' : ''}${directory.directoryPath || directory.directoryName}`
})))

const currentDraftSignature = computed(() => JSON.stringify({
  engineType: form.engineType,
  engineTarget: isDsTask.value ? form.engineTarget : pgParameterText.value.trim(),
  dsCallbackMethod: isDsTask.value ? form.dsCallbackMethod.trim() : '',
  pgCallbackMethod: isDsTask.value ? '' : form.pgCallbackMethod.trim(),
  parameterTemplate: isDsTask.value
    ? {
        projectCode: form.dsProjectCode,
        failureStrategy: form.dsFailureStrategy,
        processInstancePriority: form.dsProcessInstancePriority,
        warningType: form.dsWarningType,
        workerGroup: form.dsWorkerGroup,
        execType: form.dsExecType,
        startParamsText: dsStartParamsText.value,
        environmentCode: form.dsEnvironmentCode,
        warningGroupId: form.dsWarningGroupId
      }
    : {},
  pgParameterText: pgParameterText.value,
}))

const newDirectoryParentName = computed(() => {
  if (newDirectoryParentId.value === null) {
    return '全部'
  }
  return directories.value.find((directory) => directory.id === newDirectoryParentId.value)?.directoryName || '全部'
})

const nextTaskCode = computed(() => {
  return `${taskTotal.value + 1}`
})

const publishDisabled = computed(() => !lastTestPassed.value || testedDraftSignature.value !== currentDraftSignature.value)

const applyDsDefaults = () => {
  if (!form.dsProjectCode) {
    form.dsProjectCode = getDefaultProjectCode()
  }
  if (!form.dsFailureStrategy) {
    form.dsFailureStrategy = dsDefaults.failureStrategy || 'CONTINUE'
  }
  if (!form.dsProcessInstancePriority) {
    form.dsProcessInstancePriority = dsDefaults.processInstancePriority || 'MEDIUM'
  }
  if (!form.dsWarningType) {
    form.dsWarningType = dsDefaults.warningType || 'NONE'
  }
  form.dsWorkerGroup = dsDefaults.workerGroup || 'default'
  form.dsExecType = dsDefaults.execType || 'START_PROCESS'
  if (!form.dsEnvironmentCode) {
    form.dsEnvironmentCode = dsDefaults.defaultEnvironmentCode
  }
  if (!form.dsWarningGroupId) {
    form.dsWarningGroupId = normalizeWarningGroupValue(dsDefaults.defaultWarningGroupId)
  }
}

const getDefaultProjectCode = () => {
  return (
    dsOptions.projects.find((project) => project.name === '测试项目')?.code
    || dsDefaults.defaultProjectCode
    || dsOptions.projects[0]?.code
    || ''
  )
}

const buildPersistedTestResult = (row: TaskRow) => {
  if (row.lastTestSuccess === null || row.lastTestSuccess === undefined) {
    return null
  }
  return {
    success: Boolean(row.lastTestSuccess),
    message: row.lastTestMessage || '',
    state: row.lastTestState || null,
    workflowSummary: row.lastTestWorkflowSummary || null
  }
}

const resetForm = () => {
  Object.assign(form, createInitialForm(), { taskCode: nextTaskCode.value })
  applyDsDefaults()
  pgParameterText.value = DEFAULT_PG_TEMPLATE
  dsStartParamsText.value = DEFAULT_DS_START_PARAMS
  testResult.value = null
  lastTestPassed.value = false
  testedDraftSignature.value = ''
}

const loadTasks = async () => {
  loadingTasks.value = true
  try {
    const params: Record<string, any> = {
      page: taskPage.value,
      pageSize: taskPageSize.value
    }
    const keyword = taskKeyword.value.trim()
    if (keyword) {
      params.keyword = keyword
    }
    if (taskEngineType.value) {
      params.engineType = taskEngineType.value
    }
    if (selectedDirectoryId.value === null) {
      params.uncategorized = true
    } else if (typeof selectedDirectoryId.value === 'number') {
      params.directoryId = selectedDirectoryId.value
    }
    const { data } = await http.get('/admin/tasks', { params })
    tasks.value = data.items || []
    taskTotal.value = data.total || 0
    taskPage.value = data.page || taskPage.value
    taskPageSize.value = data.pageSize || taskPageSize.value
  } finally {
    loadingTasks.value = false
  }
}

const searchTasks = async () => {
  taskPage.value = 1
  await loadTasks()
}

const handleTaskPageSizeChange = async () => {
  taskPage.value = 1
  await loadTasks()
}

const mergeUsers = (items: any[]) => {
  const userMap = new Map(users.value.map((user) => [user.email || user.username, user]))
  items.forEach((item) => {
    const key = item.email || item.username
    if (key) {
      userMap.set(key, item)
    }
  })
  users.value = Array.from(userMap.values())
}

const getSelectedUserEmails = () => [
  ...form.notifyUserEmails,
  ...form.visibleUserEmails,
  ...form.executableUserEmails
].filter(Boolean)

const fetchUsers = async (keyword = '') => {
  const { data } = await http.get('/admin/users', {
    params: {
      keyword: keyword.trim() || undefined,
      limit: 50
    }
  })
  return data || []
}

const setUserSearchOptions = (items: any[]) => {
  const selectedEmails = new Set(getSelectedUserEmails())
  const currentUserMap = new Map(users.value.map((user) => [user.email || user.username, user]))
  const resultKeys = new Set(items.map((user) => user.email || user.username).filter(Boolean))
  const selectedUsers = Array.from(selectedEmails)
    .filter((email) => !resultKeys.has(email))
    .map((email) => currentUserMap.get(email) || { id: email, username: email, email, fullname: email })
  users.value = [...items, ...selectedUsers]
}

const searchUsers = async (keyword = '') => {
  loadingUsers.value = true
  try {
    const items = await fetchUsers(keyword)
    setUserSearchOptions(items)
  } finally {
    loadingUsers.value = false
  }
}

const loadDefaultUsers = async () => {
  if (!users.value.length) {
    await searchUsers('')
  }
}

const ensureUserOptions = async (emails: string[]) => {
  const existing = new Set(users.value.map((user) => user.email || user.username))
  const missing = Array.from(new Set(emails.filter(Boolean))).filter((email) => !existing.has(email))
  for (const email of missing) {
    mergeUsers(await fetchUsers(email))
  }
  const nextExisting = new Set(users.value.map((user) => user.email || user.username))
  mergeUsers(
    missing
      .filter((email) => !nextExisting.has(email))
      .map((email) => ({ id: email, username: email, email, fullname: email }))
  )
}

const ensureTaskUserOptions = async (row: TaskRow) => {
  await ensureUserOptions([
    ...(row.notifyUserEmails || []),
    ...(row.visibleUserEmails || []),
    ...(row.executableUserEmails || [])
  ])
}

const formatUserOption = (user: any) => {
  const fullname = user.fullname || user.username || user.email
  const email = user.email || user.username
  return `${fullname}(${email})`
}

const formatSelectedUsers = (emails: string[]) => {
  if (!emails.length) {
    return ''
  }
  const userMap = new Map(users.value.map((user) => [user.email || user.username, formatUserOption(user)]))
  return emails.map((email) => userMap.get(email) || email).join('、')
}

const loadDirectories = async () => {
  const { data } = await http.get('/admin/task-directories')
  directories.value = data
}

const loadDsConfig = async () => {
  const { data } = await http.get('/admin/ds-config')
  dsDefaults.defaultProjectCode = data.defaultProjectCode || ''
  dsDefaults.workerGroup = data.workerGroup || 'default'
  dsDefaults.failureStrategy = data.failureStrategy || 'CONTINUE'
  dsDefaults.processInstancePriority = data.processInstancePriority || 'MEDIUM'
  dsDefaults.warningType = data.warningType || 'NONE'
  dsDefaults.execType = data.execType || 'START_PROCESS'
  dsDefaults.defaultEnvironmentCode = data.defaultEnvironmentCode ? `${data.defaultEnvironmentCode}` : ''
  dsDefaults.defaultWarningGroupId = data.defaultWarningGroupId ? `${data.defaultWarningGroupId}` : ''
  dsDefaults.defaultDsCallbackMethod = data.defaultDsCallbackMethod ?? ''
  dsDefaults.defaultPgCallbackMethod = data.defaultPgCallbackMethod ?? ''
  applyDsDefaults()
}

const loadDsOptions = async () => {
  const { data } = await http.get('/admin/ds-options')
  dsOptions.projects = data.projects || []
  dsOptions.environments = data.environments || []
  dsOptions.warningGroups = data.warningGroups || []
  applyDsDefaults()
}

const buildParameterTemplate = () => {
  if (!isDsTask.value) {
    return {}
  }

  const startParams = dsStartParamsText.value.trim() ? JSON.parse(dsStartParamsText.value) : null
  const parameterTemplate: Record<string, any> = {
    projectCode: form.dsProjectCode,
    failureStrategy: form.dsFailureStrategy,
    processInstancePriority: form.dsProcessInstancePriority,
    warningType: form.dsWarningType,
    workerGroup: form.dsWorkerGroup,
    execType: form.dsExecType
  }

  parameterTemplate.startParams = startParams
  if (form.dsEnvironmentCode.trim()) {
    parameterTemplate.environmentCode = form.dsEnvironmentCode.trim()
  }
  if (form.dsWarningGroupId.trim()) {
    parameterTemplate.warningGroupId = form.dsWarningGroupId.trim()
  }
  return parameterTemplate
}

const normalizeOptionalText = (value: string | null | undefined) => {
  if (typeof value !== 'string') {
    return null
  }
  return value.trim() || null
}

const formatDirectoryName = (value?: string | null) => {
  return value?.trim() || '未分类'
}

const formatProjectOption = (option: any) => {
  return option.name || '-'
}

const formatEnvironmentOption = (option: any) => {
  return option.name || '-'
}

const formatWarningGroupOption = (option: any) => {
  return option.name || '-'
}

const normalizeWarningGroupValue = (value: any) => {
  if (value === null || value === undefined || `${value}`.trim() === '') {
    return ''
  }
  const rawValue = `${value}`.trim()
  const byId = dsOptions.warningGroups.find((option) => `${option.id}` === rawValue)
  if (byId) {
    return rawValue
  }
  const byAlertInstanceIds = dsOptions.warningGroups.find((option) => `${option.alertInstanceIds || ''}`.trim() === rawValue)
  return byAlertInstanceIds ? `${byAlertInstanceIds.id}` : rawValue
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
    await loadDirectories()
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
    await Promise.all([loadDirectories(), loadTasks()])
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(error?.response?.data?.detail || '删除目录失败')
  } finally {
    deletingDirectoryId.value = null
  }
}

const buildPayload = (publishedOverride?: boolean) => ({
  id: form.id,
  directoryId: form.directoryId,
  taskCode: form.taskCode,
  displayName: form.displayName,
  description: form.description,
  scenario: null,
  prerequisite: normalizeOptionalText(form.prerequisite),
  impactScope: normalizeOptionalText(form.impactScope),
  failureContact: formatSelectedUsers(form.notifyUserEmails),
  engineType: form.engineType,
  engineTarget: isDsTask.value ? form.engineTarget : pgParameterText.value.trim(),
  dsCallbackMethod: isDsTask.value ? normalizeOptionalText(form.dsCallbackMethod) : null,
  pgCallbackMethod: isDsTask.value ? null : normalizeOptionalText(form.pgCallbackMethod),
  parameterTemplate: buildParameterTemplate(),
  repeatWindowMinutes: form.repeatWindowMinutes ?? null,
  executionWindowCron: normalizeOptionalText(form.executionWindowCron),
  visibleUserEmails: form.visibleUserEmails,
  executableUserEmails: form.executableUserEmails,
  notifyUserEmails: form.notifyUserEmails,
  published: publishedOverride ?? form.published
})

const formatRequestError = (error: any, fallback: string) => {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const path = Array.isArray(item?.loc) ? item.loc.filter((value: string) => value !== 'body').join('.') : ''
        return path ? `${path}: ${item?.msg || JSON.stringify(item)}` : item?.msg || JSON.stringify(item)
      })
      .join('；')
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (error instanceof SyntaxError) {
    return `JSON 格式错误：${error.message}`
  }
  if (error?.message) {
    return `${fallback}：${error.message}`
  }
  return fallback
}

const syncFormFromTask = (row: TaskRow) => {
  const parameterTemplate = row.parameterTemplate || {}
  Object.assign(form, createInitialForm(), {
    ...row,
    dsProjectCode: parameterTemplate.projectCode || dsDefaults.defaultProjectCode,
    dsFailureStrategy: parameterTemplate.failureStrategy || dsDefaults.failureStrategy,
    dsProcessInstancePriority: parameterTemplate.processInstancePriority || dsDefaults.processInstancePriority,
    dsWarningType: parameterTemplate.warningType || dsDefaults.warningType,
    dsWorkerGroup: dsDefaults.workerGroup || 'default',
    dsExecType: dsDefaults.execType || 'START_PROCESS',
    dsEnvironmentCode: parameterTemplate.environmentCode ? `${parameterTemplate.environmentCode}` : dsDefaults.defaultEnvironmentCode,
    dsWarningGroupId: normalizeWarningGroupValue(parameterTemplate.warningGroupId || dsDefaults.defaultWarningGroupId),
    dsCallbackMethod: row.dsCallbackMethod || ''
  })

  if (row.engineType === 'DS') {
    dsStartParamsText.value = parameterTemplate.startParams ? JSON.stringify(parameterTemplate.startParams, null, 2) : DEFAULT_DS_START_PARAMS
    pgParameterText.value = DEFAULT_PG_TEMPLATE
  } else {
    pgParameterText.value = row.engineTarget || ''
    form.pgCallbackMethod = row.pgCallbackMethod || ''
    dsStartParamsText.value = DEFAULT_DS_START_PARAMS
    applyDsDefaults()
  }

  testResult.value = buildPersistedTestResult(row)
  lastTestPassed.value = Boolean(row.lastTestSuccess)
  testedDraftSignature.value = lastTestPassed.value ? currentDraftSignature.value : ''
}

const editTask = async (row: TaskRow) => {
  try {
    const { data } = await http.get(`/admin/tasks/${row.id}`)
    await ensureTaskUserOptions(data)
    syncFormFromTask(data)
  } catch (error: any) {
    ElMessage.error(formatRequestError(error, '加载任务详情失败'))
  }
}

const saveTask = async () => {
  try {
    saving.value = true
    const { data } = await http.post('/admin/tasks', buildPayload(false))
    ElMessage.success('任务配置保存成功')
    await loadTasks()
    await ensureTaskUserOptions(data)
    syncFormFromTask(data)
  } catch (error: any) {
    ElMessage.error(formatRequestError(error, '保存失败，请检查表单和 JSON 配置'))
  } finally {
    saving.value = false
  }
}

const testTask = async () => {
  try {
    testing.value = true
    const { data } = await http.post('/admin/tasks/test-execution', buildPayload(false), LONG_RUNNING_REQUEST_CONFIG)
    testResult.value = data
    lastTestPassed.value = Boolean(data.success)
    testedDraftSignature.value = data.success ? currentDraftSignature.value : ''
    if (data.success) {
      ElMessage.success(data.message)
    } else {
      ElMessage.error(data.message)
    }
  } catch (error: any) {
    lastTestPassed.value = false
    testedDraftSignature.value = ''
    ElMessage.error(formatRequestError(error, '执行测试失败，请检查执行配置和任务参数'))
  } finally {
    testing.value = false
  }
}

const publishTask = async () => {
  try {
    publishing.value = true
    const { data } = await http.post('/admin/tasks', buildPayload(true))
    ElMessage.success('任务已发布到任务中心')
    await loadTasks()
    await ensureTaskUserOptions(data)
    syncFormFromTask(data)
  } catch (error: any) {
    ElMessage.error(formatRequestError(error, '发布失败，请先对当前配置执行测试并成功'))
  } finally {
    publishing.value = false
  }
}

const removeTask = async (row: TaskRow) => {
  try {
    await ElMessageBox.confirm(
      `删除后不可恢复。系统会同时删除该任务配置、测试结果、执行记录，以及任务中心中的对应按钮；后续任务编码会自动重排。确认删除“${row.displayName}”吗？`,
      '删除任务',
      { type: 'warning' }
    )
    await http.delete(`/admin/tasks/${row.id}`)
    ElMessage.success('任务已删除')
    await loadTasks()
    resetForm()
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(formatRequestError(error, '删除任务失败'))
  }
}

watch(selectedDirectoryId, async () => {
  taskPage.value = 1
  await loadTasks()
})

onMounted(async () => {
  await Promise.all([loadTasks(), loadDirectories(), loadDsConfig(), loadDsOptions()])
  resetForm()
})
</script>

<style scoped>
.admin-grid {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) minmax(0, 1.08fr);
  gap: 12px;
  align-items: start;
}

.admin-grid > .glass-card {
  min-width: 0;
}

.configured-tasks-card {
  order: 1;
}

.task-config-card {
  order: 2;
}

.task-config-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.required-mark {
  margin-right: 4px;
  color: #d92d20;
  font-weight: 700;
}

.label-with-help {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.help-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: rgba(62, 111, 244, 0.12);
  color: #3e6ff4;
  font-size: 11px;
  font-weight: 700;
  cursor: help;
}

.subsection-title {
  font-size: 15px;
  font-weight: 700;
}

.subsection-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.subsection-desc {
  margin: 6px 0 14px;
}

.field-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
}

.action-row {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.table-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.configured-task-layout {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.task-list-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 120px auto;
  gap: 8px;
  align-items: center;
}

.task-pagination {
  justify-content: flex-end;
}

.configured-tasks-card :deep(.el-card__body) {
  padding: 12px;
}

.test-result {
  margin-top: 18px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.test-result.is-success {
  background: rgba(24, 140, 84, 0.08);
}

.test-result.is-failed {
  background: rgba(191, 49, 49, 0.08);
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.result-message {
  margin-top: 10px;
  line-height: 1.7;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.result-item {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.5);
}

.table-actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0;
  white-space: nowrap;
}

.task-table {
  width: 100%;
}

.task-table :deep(.el-scrollbar__view) {
  min-width: 100%;
}

.task-table :deep(.el-button.is-text) {
  min-height: 22px;
  padding: 0 2px;
  font-size: 12px;
}

.task-table :deep(.el-table__cell) {
  padding: 6px 0;
}

.task-table :deep(.cell) {
  display: block;
  overflow: hidden;
  padding: 0 3px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-table :deep(.el-tag) {
  max-width: 100%;
  height: 20px;
  padding: 0 4px;
  font-size: 12px;
  line-height: 18px;
}

@media (max-width: 1280px) {
  .admin-grid {
    grid-template-columns: 1fr;
  }

  .directory-panel {
    position: static;
  }
}

@media (max-width: 780px) {
  .configured-task-layout {
    grid-template-columns: 1fr;
  }

  .directory-panel {
    position: static;
  }

  .result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
