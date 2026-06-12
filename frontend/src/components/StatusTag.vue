<template>
  <el-tag :type="type">{{ status }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const type = computed(() => {
  if (props.status === 'SUCCEEDED') return 'success'
  if (props.status === 'FAILED') return 'danger'
  if (props.status === 'RUNNING') return 'warning'
  return 'info'
})
</script>
