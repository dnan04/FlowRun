# 业务自助跑数平台

基于 `FastAPI + PostgreSQL + Vue 3 + Element Plus` 的业务自助跑数平台。平台用于让被授权的业务用户在任务中心自助触发数据处理任务，同时让管理员统一维护任务目录、任务配置、授权范围、执行规则、发布状态和执行记录。

平台当前涉及三类数据库或外部调用：

- **平台数据库**：存放平台自身配置和记录，例如管理员、目录、任务配置、授权关系、DolphinScheduler 下拉选项、执行记录和审计日志。
- **PG 执行库**：仅当任务执行方式为 `PG 存储过程` 时连接，用于调用指定 PostgreSQL 数据库中的 `CALL` 语句和可选后置方法。
- **DolphinScheduler**：仅当任务执行方式为 `DS 工作流` 时调用，用于启动并轮询 DS 流程实例。

## 技术栈

- 后端：FastAPI、SQLAlchemy、Pydantic Settings、python-jose、psycopg2、Uvicorn
- 前端：Vue 3、Vue Router、Pinia、Element Plus、Axios、Vite、TypeScript
- 数据库：PostgreSQL
- 部署参考：`deploy/backend.service.example`、`deploy/nginx.conf.example`

## 项目结构

```text
backend/
  app/
    api/              # FastAPI 路由
    core/             # 配置与鉴权
    db/               # 数据库连接、schema 创建和运行期兼容补齐
    models/           # SQLAlchemy 模型
    schemas/          # Pydantic 入参/出参模型
    services/         # 任务、执行、人员、PG、DS、审计等业务逻辑
  scripts/            # 本地启动脚本
  tests/              # 后端单元测试
  .env.example        # 后端配置模板
frontend/
  src/
    api/              # Axios 实例
    components/       # 通用组件
    layout/           # 主布局
    router/           # 前端路由与 URL 参数登录
    stores/           # Pinia 登录态
    views/            # 任务中心、管理后台
deploy/               # systemd 与 nginx 示例
docs/                 # 架构说明
```

## 主要功能

- **URL 参数登录**：前端通过 `?user=` 发起登录，后端按用户身份签发 Bearer Token。
- **任务中心**：业务用户查看可见或可执行任务，查看任务执行日志，执行已授权任务。
- **管理后台**：管理员维护任务目录、任务配置、执行方式、授权人员、通知人员、测试状态、发布状态和任务中心展示状态。
- **目录管理**：支持根目录、二级目录、三级目录，最多三级。
- **双执行引擎**：支持 `DS 工作流` 与 `PG 存储过程`。
- **权限控制**：可见人员只能查看任务；可执行人员可查看并执行任务；管理员可查看和维护全部任务。
- **发布前测试**：DS/PG 执行配置必须先测试成功，才能发布任务。
- **执行防护**：支持 5 段 Cron 执行时间窗口，以及基于 `PENDING/RUNNING` 记录的重复触发拦截。
- **审计与记录**：执行申请、执行完成、任务配置、目录变更等关键动作会写入平台记录 schema。

## 登录与访问

前端没有独立登录页，使用 URL 参数登录：

```text
http://localhost:5173/?user=finereport_manage
http://localhost:5173/?user=用户邮箱或用户名
```

登录成功后前端保存 Bearer Token，并按角色跳转：

- 管理员：`/admin/tasks`
- 普通用户：`/tasks`

后端登录规则：

- 用户名或 email 存在于外部人员视图：进入任务中心，视为普通用户。
- 用户名存在于平台表 `sys_admin_user`：进入管理后台，视为管理员。
- `finereport_manage` 会按管理员用户处理；首次登录时会自动创建对应管理员记录。

后端 API 前缀默认为 `/api/v1`：

```text
GET /health
GET /api/v1/openapi.json
```

## 本地启动

### 后端

首次部署时，基于模板创建真实配置文件：

```powershell
cd E:\WorkFile\VSCodeProject\FlowRun\backend
Copy-Item .env.example .env
```

真实配置只维护在 `backend/.env` 中，不应提交真实密码或 Token。本文档只说明配置项，不包含真实 `.env` 内容。

安装依赖并启动：

```powershell
cd E:\WorkFile\VSCodeProject\FlowRun\backend
D:/Anaconda_envs/envs/py311_ai/python.exe -m pip install -r requirements.txt
D:/Anaconda_envs/envs/py311_ai/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

也可以使用脚本：

```powershell
cd E:\WorkFile\VSCodeProject\FlowRun\backend
.\scripts\start.ps1
```

后端启动时会：

- 创建 `PLATFORM_CONFIG_SCHEMA` 和 `PLATFORM_RECORD_SCHEMA`。
- 执行 SQLAlchemy `create_all` 创建缺失表。
- 执行运行期兼容逻辑，补齐当前代码需要的缺失字段或索引。
- 初始化默认目录、DS 元数据下拉选项和默认管理员 `admin`。

### 前端

```powershell
cd E:\WorkFile\VSCodeProject\FlowRun\frontend
npm.cmd install
npm.cmd run dev
```

前端开发服务默认监听 `5173`，并将 `/api` 代理到 `http://127.0.0.1:8000`。

生产构建：

```powershell
cd E:\WorkFile\VSCodeProject\FlowRun\frontend
npm.cmd run build
```

## 环境配置

配置文件由后端 `pydantic-settings` 从 `backend/.env` 读取，模板见 `backend/.env.example`。

### 基础配置

```env
APP_NAME=DataRunner Platform
APP_VERSION=1.0.0
API_V1_PREFIX=/api/v1
SECRET_KEY=replace-with-production-secret
ACCESS_TOKEN_EXPIRE_MINUTES=480
ALGORITHM=HS256
CORS_ORIGINS=["http://localhost:5173"]
```

### 平台数据库

```env
PLATFORM_DB_HOST=127.0.0.1
PLATFORM_DB_PORT=5432
PLATFORM_DB_DATABASE=postgres
PLATFORM_DB_USERNAME=postgres
PLATFORM_DB_PASSWORD=postgres
PLATFORM_DB_SSLMODE=prefer
PLATFORM_CONFIG_SCHEMA=dr_config
PLATFORM_RECORD_SCHEMA=dr_record
```

- `PLATFORM_CONFIG_SCHEMA`：保存管理员、目录、任务定义、任务授权、DS 下拉元数据等配置类数据。
- `PLATFORM_RECORD_SCHEMA`：保存任务执行记录、审计日志等记录类数据。

### 外部人员视图

管理后台任务配置中的可见人员、可执行人员、失败联系人候选项来自外部 PostgreSQL 人员视图。

```env
REPORT_USER_DB_HOST=
REPORT_USER_DB_PORT=5432
REPORT_USER_DB_DATABASE=
REPORT_USER_DB_USERNAME=
REPORT_USER_DB_PASSWORD=
REPORT_USER_DB_SSLMODE=prefer
REPORT_USER_SCHEMA=public
REPORT_USER_VIEW_NAME=report_department_user_list
REPORT_USER_USERNAME_COLUMN=username
REPORT_USER_FULLNAME_COLUMN=fullname
REPORT_USER_EMAIL_COLUMN=email
```

平台使用规范化后的 email 作为业务用户标识；前端人员选项展示为 `fullname(email)`。

### PG 存储过程执行库

仅当任务执行方式为 `PG 存储过程` 时使用：

```env
PG_EXECUTION_HOST=127.0.0.1
PG_EXECUTION_PORT=5432
PG_EXECUTION_DATABASE=postgres
PG_EXECUTION_USERNAME=postgres
PG_EXECUTION_PASSWORD=postgres
PG_EXECUTION_SSLMODE=prefer
TASK_DEFAULT_PG_CALLBACK_METHOD=SELECT * FROM public.get_user_rank(:job_instance_name) ;
```

任务配置中的存储过程必须填写 `CALL` 语句，可填写多条，分隔符只支持英文分号 `;`：

```sql
call public.p_new_time(:job_instance_name); call public.p_sync_data();
```

`:job_instance_name` 是可选占位符。执行时平台会用任务名称和 17 位时间戳生成实例名并替换到 SQL 中。

PG 后置方法可不填；如果填写，必须是一条包含 `:job_instance_name` 的 `SELECT` 语句。后置方法返回空结果视为成功，返回非空结果会作为失败信息输出。

### DolphinScheduler

仅当任务执行方式为 `DS 工作流` 时使用：

```env
DOLPHINSCHEDULER_BASE_URL=http://dolphinscheduler.example/api
DOLPHINSCHEDULER_ACCESS_TOKEN=
DOLPHINSCHEDULER_TENANT_CODE=default
DOLPHINSCHEDULER_TIMEOUT_SECONDS=30
DOLPHINSCHEDULER_ENABLED=true
DOLPHINSCHEDULER_PROJECT_CODE=
DOLPHINSCHEDULER_WORKER_GROUP=default
DOLPHINSCHEDULER_FAILURE_STRATEGY=CONTINUE
DOLPHINSCHEDULER_PROCESS_INSTANCE_PRIORITY=MEDIUM
DOLPHINSCHEDULER_WARNING_TYPE=NONE
DOLPHINSCHEDULER_EXEC_TYPE=START_PROCESS
DOLPHINSCHEDULER_ENVIRONMENT_CODE=
DOLPHINSCHEDULER_WARNING_GROUP_ID=
TASK_DEFAULT_DS_CALLBACK_METHOD=SELECT * FROM public.get_user_rank(:job_instance_name) ;
```

管理后台 DS 任务配置包括：

- `流程定义编码`：对应 DS `processDefinitionCode`。
- `projectCode`：可来自任务配置，也可来自 `DOLPHINSCHEDULER_PROJECT_CODE` 默认值。
- `failureStrategy`、`processInstancePriority`、`warningType`、`workerGroup`、`execType`：可来自任务参数或环境配置默认值。
- `startParams(JSON)`：可选，必须是 JSON 对象。
- `environmentCode`、`warningGroupId`：可选，下拉选项来自平台表 `ds_environment`、`ds_alertgroup`。
- `后置方法`：DS 流程成功后调用 PG 执行库中的 PostgreSQL 方法，必须包含 `:job_instance_name`。

DS 启动后，平台会优先使用返回的实例 ID 查询实例；如启动接口未返回实例 ID，会按当前 DS token 用户和启动时间回查最近实例，并轮询到成功或失败状态。

## 数据表

平台按 schema 拆分配置数据与记录数据。

`PLATFORM_CONFIG_SCHEMA`：

- `sys_admin_user`：管理员账号。
- `dr_task_directory`：任务目录。
- `dr_task_definition`：任务定义、执行配置、测试状态、发布状态和任务中心状态。
- `dr_task_visible_user`：可见人员授权关系。
- `dr_task_execute_user`：可执行人员授权关系。
- `dr_task_notify_user`：通知人员关系。
- `ds_project`、`ds_environment`、`ds_alertgroup`：DolphinScheduler 下拉选项元数据。

`PLATFORM_RECORD_SCHEMA`：

- `dr_task_execution`：任务执行记录。
- `dr_audit_log`：管理操作、执行动作和系统初始化审计日志。

默认初始化内容：

- 目录：物流、财务、供应链。
- 管理员：`admin`。
- DS 元数据：若对应表为空，会插入内置示例项目、环境和告警组。

## 任务配置与发布规则

任务保存后会进入“已配置任务”，但不会自动出现在任务中心。发布到任务中心的基本流程：

1. 管理员在管理后台配置任务。
2. 执行测试。
3. 当前执行配置测试成功后发布任务。
4. 在任务中心通过“添加任务”把已发布任务加入任务中心。

执行相关配置变化后，旧测试结果会失效，需要重新测试后才能发布。执行相关配置包括：

- DS 工作流：执行方式、流程定义编码、`projectCode`、`failureStrategy`、`processInstancePriority`、`warningType`、`workerGroup`、`execType`、`startParams`、`environmentCode`、`warningGroupId`、后置方法。
- PG 存储过程：执行方式、存储过程、后置方法。

非执行配置变化不会清空已有测试状态和发布状态，例如目录、失败联系人、可见人员、可执行人员、影响范围、执行前提、重复触发窗口、用户允许执行时间等。

从任务中心移除任务只会取消任务中心展示，不会删除任务定义或历史执行记录。删除已配置任务会删除任务配置、授权关系和关联执行记录，并重新整理后续任务编码。

## API 概览

所有业务 API 默认挂载在 `/api/v1` 下：

- `POST /auth/login`：按用户名或 email 登录。
- `GET /auth/me`：获取当前登录用户。
- `GET /tasks/my`：获取当前用户可见任务。
- `GET /tasks/directories`：获取当前用户可见目录。
- `GET /tasks/executions/my`：获取当前用户执行记录。
- `GET /tasks/{task_id}/executions`：获取指定任务执行记录。
- `POST /tasks/{task_id}/execute`：执行任务。
- `GET /admin/tasks`：管理员获取全部任务。
- `POST /admin/tasks`：管理员新增或更新任务。
- `DELETE /admin/tasks/{task_id}`：管理员删除任务。
- `POST /admin/tasks/{task_id}/add-to-center`：添加任务到任务中心。
- `POST /admin/tasks/{task_id}/remove-from-center`：从任务中心移除任务。
- `POST /admin/tasks/test-execution`：测试任务执行配置。
- `GET /admin/task-directories`：管理员获取目录。
- `POST /admin/task-directories`：管理员创建目录。
- `PUT /admin/task-directories/{directory_id}`：管理员重命名目录。
- `DELETE /admin/task-directories/{directory_id}`：管理员删除目录。
- `GET /admin/users`：获取外部人员候选项。
- `GET /admin/executions`：管理员查看全部执行记录。
- `GET /admin/ds-config`：获取 DS 默认配置。
- `GET /admin/ds-options`：获取 DS 下拉选项。
- `GET /dashboard/summary`：平台看板摘要。

## 测试与检查

后端单元测试：

```powershell
cd E:\WorkFile\VSCodeProject\FlowRun\backend
D:/Anaconda_envs/envs/py311_ai/python.exe -m unittest tests.test_task_code_rules tests.test_dolphinscheduler_instance_selection
```

前端构建：

```powershell
cd E:\WorkFile\VSCodeProject\FlowRun\frontend
npm.cmd run build
```

## Docker 单容器部署

项目根目录提供 `Dockerfile`，会在构建阶段编译前端，并在运行阶段使用同一个容器启动 nginx 和 FastAPI 后端。

构建镜像：

```bash
docker build -t flowrun:latest .
```

启动容器，宿主机端口使用 `5002`：

```bash
docker run -d --name flowrun --env-file backend/.env -p 5002:80 flowrun:latest
```

访问地址：

```text
http://服务器IP:5002/?user=finereport_manage
```

## 部署参考

后端 systemd 示例：

```text
deploy/backend.service.example
```

前端构建产物默认位于：

```text
frontend/dist
```

nginx 示例会将静态资源指向 `frontend/dist`，并将 `/api/` 反向代理到 `http://127.0.0.1:8000/api/`：

```text
deploy/nginx.conf.example
```

## 注意事项

- `backend/.env` 是真实配置文件，不应提交真实密码或 Token。
- `backend/.env.example` 是配置模板，不应放真实密钥。
- `.gitignore` 已忽略 `.env` 和 `backend/.env`。
- 外部人员库、PG 执行库、DolphinScheduler 与平台库相互独立；平台库只保存平台配置、授权快照、执行记录和审计记录。
- 仓库根目录存在 `platform_data_backup.dump`，用于平台数据备份场景，使用前请确认目标数据库与 schema。
