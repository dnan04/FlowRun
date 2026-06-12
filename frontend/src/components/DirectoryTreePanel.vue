<template>
  <aside class="directory-panel">
    <div class="directory-header">
      <span>目录</span>
      <el-button v-if="canManage" text type="primary" @click="$emit('create', null)">新建</el-button>
    </div>

    <div class="directory-tree">
      <button
        class="directory-item directory-root"
        :class="{ active: modelValue === 'all' }"
        :data-count="tasks.length"
        data-directory-root="true"
        aria-label="全部目录"
        @click="$emit('update:modelValue', 'all')"
      >
        <span class="directory-name" title="全部">全部</span>
      </button>

      <template v-for="directory in directoryTree" :key="directory.id">
        <div class="directory-row">
          <button
            class="directory-item directory-level-2"
            :class="{ active: modelValue === directory.id }"
            :data-count="getDirectoryTaskCount(directory.id)"
            @click="$emit('update:modelValue', directory.id)"
          >
            <span
              class="directory-caret"
              :class="{
                visible: hasChildren(directory),
                expanded: isExpanded(directory.id)
              }"
              aria-hidden="true"
              @click.stop="toggleDirectory(directory)"
            />
            <el-icon class="directory-folder-icon"><Folder /></el-icon>
            <span class="directory-name" :title="directory.directoryName">{{ directory.directoryName }}</span>
          </button>
          <el-button
            v-if="canManage"
            class="directory-tool directory-tool-add"
            text
            size="small"
            title="新增子目录"
            @click.stop="$emit('create', directory.id)"
          >
            <el-icon><Plus /></el-icon>
          </el-button>
          <el-button
            v-if="canManage"
            class="directory-tool directory-tool-edit"
            text
            size="small"
            title="重命名"
            @click.stop="$emit('rename', directory)"
          >
            <el-icon><Edit /></el-icon>
          </el-button>
          <el-button
            v-if="canManage"
            class="directory-tool directory-tool-delete"
            text
            type="danger"
            size="small"
            :loading="deletingDirectoryId === directory.id"
            title="删除"
            @click.stop="$emit('delete', directory)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>

        <div v-for="child in visibleChildren(directory)" :key="child.id" class="directory-row">
          <button
            class="directory-item directory-level-3"
            :class="{ active: modelValue === child.id }"
            :data-count="getDirectoryTaskCount(child.id)"
            @click="$emit('update:modelValue', child.id)"
          >
            <el-icon class="directory-folder-icon"><Folder /></el-icon>
            <span class="directory-name" :title="child.directoryName">{{ child.directoryName }}</span>
          </button>
          <el-button
            v-if="canManage"
            class="directory-tool directory-tool-add"
            text
            size="small"
            title="新增子目录"
            @click.stop="$emit('create', child.id)"
          >
            <el-icon><Plus /></el-icon>
          </el-button>
          <el-button
            v-if="canManage"
            class="directory-tool directory-tool-edit"
            text
            size="small"
            title="重命名"
            @click.stop="$emit('rename', child)"
          >
            <el-icon><Edit /></el-icon>
          </el-button>
          <el-button
            v-if="canManage"
            class="directory-tool directory-tool-delete"
            text
            type="danger"
            size="small"
            :loading="deletingDirectoryId === child.id"
            title="删除"
            @click.stop="$emit('delete', child)"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </template>

      <div v-if="showUncategorizedDirectory" class="directory-row">
        <button
          class="directory-item directory-level-2"
          :class="{ active: modelValue === null }"
          :data-count="uncategorizedTaskCount"
          @click="$emit('update:modelValue', null)"
        >
          <span class="directory-caret" aria-hidden="true" />
          <el-icon class="directory-folder-icon"><Folder /></el-icon>
          <span class="directory-name" title="未分类">未分类</span>
        </button>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Delete, Edit, Folder, Plus } from '@element-plus/icons-vue'

type DirectorySelection = number | 'all' | null
type DirectoryNode = Record<string, any> & {
  id: number
  directoryName: string
  parentDirectoryId?: number | null
  children?: DirectoryNode[]
}

const props = defineProps<{
  modelValue: DirectorySelection
  directories: DirectoryNode[]
  tasks: Record<string, any>[]
  canManage?: boolean
  deletingDirectoryId?: number | null
}>()

const collapsedDirectoryIds = ref(new Set<number>())

defineEmits<{
  (event: 'update:modelValue', value: DirectorySelection): void
  (event: 'create', parentId: number | null): void
  (event: 'rename', directory: DirectoryNode): void
  (event: 'delete', directory: DirectoryNode): void
}>()

const directoryTree = computed(() => {
  const nodes = props.directories.map((item) => ({ ...item, children: [] as DirectoryNode[] }))
  const nodeMap = new Map(nodes.map((item) => [item.id, item]))
  const roots: DirectoryNode[] = []
  nodes.forEach((item) => {
    if (item.parentDirectoryId && nodeMap.has(item.parentDirectoryId)) {
      nodeMap.get(item.parentDirectoryId)?.children?.push(item)
    } else {
      roots.push(item)
    }
  })
  return roots
})

const uncategorizedTaskCount = computed(() => {
  return props.tasks.filter((task) => (task.directoryId ?? null) === null).length
})

const showUncategorizedDirectory = computed(() => {
  return Boolean(props.canManage) || uncategorizedTaskCount.value > 0
})

const collectDirectoryIds = (directoryId: number) => {
  const ids = [directoryId]
  const appendChildren = (parentId: number) => {
    props.directories
      .filter((directory) => directory.parentDirectoryId === parentId)
      .forEach((directory) => {
        ids.push(directory.id)
        appendChildren(directory.id)
      })
  }
  appendChildren(directoryId)
  return ids
}

const getDirectoryTaskCount = (directoryId: number) => {
  const directoryIds = collectDirectoryIds(directoryId)
  return props.tasks.filter((task) => directoryIds.includes(task.directoryId)).length
}

const hasChildren = (directory: DirectoryNode) => Boolean(directory.children?.length)

const isExpanded = (directoryId: number) => !collapsedDirectoryIds.value.has(directoryId)

const visibleChildren = (directory: DirectoryNode) => {
  return isExpanded(directory.id) ? directory.children || [] : []
}

const toggleDirectory = (directory: DirectoryNode) => {
  if (!hasChildren(directory)) {
    return
  }
  const next = new Set(collapsedDirectoryIds.value)
  if (next.has(directory.id)) {
    next.delete(directory.id)
  } else {
    next.add(directory.id)
  }
  collapsedDirectoryIds.value = next
}
</script>

<style scoped>
.directory-panel {
  position: sticky;
  top: 0;
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 6px 18px rgba(31, 45, 61, 0.07);
}

.directory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 34px;
  padding: 0 0 10px 12px;
  border-bottom: 1px solid var(--line);
  color: #1f2d3d;
  font-weight: 700;
}

.directory-header :deep(.el-button) {
  padding: 4px 6px;
  color: var(--brand);
  font-weight: 700;
}

.directory-header :deep(.el-button)::before {
  margin-right: 4px;
  content: "+";
  font-size: 18px;
  line-height: 1;
}

.directory-tree {
  display: grid;
  gap: 3px;
}

.directory-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 22px 22px 22px;
  align-items: center;
  gap: 2px;
}

.directory-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-width: 0;
  min-height: 32px;
  padding: 6px 34px 6px 0;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #31435a;
  font-size: 14px;
  line-height: 20px;
  text-align: left;
  background: transparent;
  cursor: pointer;
  transition:
    background 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease;
}

.directory-caret {
  flex: 0 0 8px;
  width: 0;
  height: 0;
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  border-left: 5px solid #9aa8bd;
  opacity: 0;
  transition: transform 0.14s ease;
}

.directory-caret.visible {
  opacity: 1;
}

.directory-caret.expanded {
  transform: rotate(90deg);
}

.directory-folder-icon {
  flex: 0 0 auto;
  color: #8ea1ba;
  font-size: 15px;
}

.directory-name {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.directory-item.active .directory-folder-icon {
  color: rgba(255, 255, 255, 0.82);
}

.directory-item.active .directory-caret {
  border-left-color: rgba(255, 255, 255, 0.82);
}

.directory-root {
  padding-left: 12px;
  font-weight: 700;
}

.directory-level-2,
.directory-level-3 {
  position: relative;
}

.directory-level-2 {
  padding-left: 20px;
}

.directory-level-3 {
  padding-left: 48px;
}

.directory-level-2::after,
.directory-level-3::after,
.directory-root::after {
  position: absolute;
  top: 50%;
  right: 8px;
  min-width: 16px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  color: #2f8bff;
  font-size: 12px;
  line-height: 18px;
  text-align: center;
  background: #e8f3ff;
  transform: translateY(-50%);
  content: attr(data-count);
}

.directory-item:hover,
.directory-item.active {
  border-color: transparent;
  background: #f4f8ff;
}

.directory-item.active {
  color: #fff;
  background: var(--brand);
  box-shadow: 0 6px 12px rgba(47, 102, 232, 0.24);
}

.directory-item.active::after {
  color: var(--brand);
  background: #fff;
}

.directory-tool {
  position: relative;
  width: 22px;
  min-height: 22px;
  margin-left: 0 !important;
  padding: 0;
  border-radius: 4px;
  color: #58a6ff;
  font-size: 0;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.14s ease, background 0.14s ease;
}

.directory-row:hover .directory-tool,
.directory-tool:focus-visible {
  opacity: 1;
  pointer-events: auto;
}

.directory-tool:hover {
  background: #e8f3ff;
}

.directory-tool :deep(.el-icon) {
  font-size: 15px;
}

.directory-tool-delete {
  color: #ff5a5f;
}

.directory-tool-delete:hover {
  background: #fff0f0;
}

@media (max-width: 1280px) {
  .directory-panel {
    position: static;
  }
}

@media (max-width: 1020px) {
  .directory-panel {
    grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
  }

  .directory-header {
    grid-column: 1 / -1;
  }
}
</style>
