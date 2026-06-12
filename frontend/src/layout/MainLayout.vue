<template>
  <div class="page-shell top-shell">
    <header class="top-bar">
      <nav class="nav-list">
        <router-link to="/tasks" class="nav-item">任务中心</router-link>
        <router-link v-if="auth.isAdmin" to="/admin/tasks" class="nav-item">管理后台</router-link>
      </nav>

      <div class="brand-block">
        <div class="brand-kicker">
          <span class="brand-dot"></span>
          <p class="eyebrow">Data Runner</p>
        </div>
        <h1>业务自助跑数平台</h1>
        <p class="meta-text brand-text">统一授权、统一执行、统一追踪，让业务方自助跑数可控可审计。</p>
      </div>
    </header>

    <main class="content-panel">
      <div class="content-inner">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
</script>

<style scoped>
.top-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 0;
  height: 100vh;
  padding: 0;
  overflow: hidden;
}

.top-bar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(360px, auto);
  align-items: center;
  gap: 24px;
  width: 100%;
  margin: 0 auto;
  min-height: 64px;
  padding: 0 24px;
  border-bottom: 1px solid var(--line);
  background: #fff;
  box-shadow: 0 1px 8px rgba(31, 45, 61, 0.04);
}

.brand-block {
  min-width: 0;
  justify-self: end;
  text-align: right;
}

.brand-kicker {
  display: none;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.brand-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--accent), #dd9b54);
  box-shadow: 0 0 0 6px rgba(196, 123, 45, 0.12);
}

.eyebrow {
  margin: 0;
  color: var(--accent);
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

h1 {
  margin: 0 0 4px;
  font-size: 18px;
  line-height: 1.25;
  color: #16233a;
}

.brand-text {
  margin: 0;
  line-height: 1.45;
  font-size: 12px;
}

.nav-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  align-self: stretch;
  gap: 2px;
  min-width: 0;
}

.nav-item {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding: 0 24px;
  border: 0;
  border-radius: 0;
  color: #4b5d78;
  text-decoration: none;
  background: transparent;
  box-shadow: none;
  transition:
    background 0.18s ease,
    color 0.18s ease;
  white-space: nowrap;
  font-weight: 600;
  font-size: 15px;
}

.nav-item:hover {
  background: #f6f9ff;
  color: var(--brand);
}

.nav-item.router-link-active {
  background: transparent;
  color: var(--brand);
  box-shadow: inset 0 -3px 0 var(--brand);
}

.content-panel {
  min-width: 0;
  overflow: auto;
  padding: 20px 16px 0 0;
  scrollbar-gutter: stable;
}

.content-inner {
  width: min(100%, 1880px);
  margin: 0 auto;
  padding: 0 0 20px;
}

@media (max-width: 1360px) {
  .top-shell {
    padding: 0;
  }

  .top-bar {
    grid-template-columns: 1fr;
    gap: 10px;
    width: 100%;
    padding: 12px 18px;
  }

  .nav-list {
    justify-content: flex-start;
  }

  .brand-block {
    justify-self: start;
    text-align: left;
  }
}

@media (max-width: 780px) {
  .top-shell {
    padding: 0;
    gap: 12px;
  }

  .top-bar {
    padding: 10px 14px;
  }

  h1 {
    font-size: 18px;
  }

  .nav-list {
    justify-content: stretch;
  }

  .nav-item {
    flex: 1 1 calc(50% - 10px);
    min-height: 40px;
    text-align: center;
    justify-content: center;
  }
}
</style>
