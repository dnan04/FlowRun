# 架构说明

## 总体分层

- `frontend`
  - 登录页
  - 任务中心
  - 执行记录
  - 管理后台
- `backend`
  - `auth`：登录、JWT、当前用户
  - `task`：任务查询、任务配置、授权控制
  - `execution`：执行申请、防重拦截、状态落库、实例追踪
  - `audit`：关键操作留痕
  - `integration`：DS / PG 执行引擎抽象

## 关键能力

### 1. 业务前台

- 仅展示当前用户被授权可见的任务
- 展示任务说明、适用场景、执行前提、影响范围、失败联系人
- 支持填写业务日期并提交执行
- 展示最近执行结果和状态

### 2. 管理后台

- 维护任务基础信息
- 配置执行方式：`DS` 或 `PG`
- 配置参数模板
- 配置可见人员、执行人员、通知对象
- 配置发布状态和重复执行拦截窗口

### 3. 风险控制

- 执行防重：在任务防重窗口内阻止重复点击
- 权限隔离：按用户授权可见和可执行
- 审计日志：保留任务发起和配置变更记录
- 技术封装：业务侧不暴露底层 DS / PG 技术细节

## 数据存储

平台数据统一存储在 `.env` 配置的 PostgreSQL 平台库中，并按用途拆分到配置 schema 与记录 schema：

- `sys_user / sys_role / sys_permission`
- `dr_task_definition`
- `dr_task_visible_user / dr_task_execute_user / dr_task_notify_user`
- `dr_task_execution`
- `dr_audit_log`

## 执行引擎抽象

当前版本提供统一任务模型：

- 任务名称
- 执行方式
- 发起人
- 发起时间
- 执行状态
- 结果摘要
- 实例号

当前代码内为模拟执行器，后续可以在 `execution_service.py` 中替换为：

- DolphinScheduler API 调用
- PostgreSQL 存储过程执行

对前端和业务侧保持无感知。
