# 业务自助跑数平台

基于 `FastAPI + PostgreSQL + Vue 3 + Element Plus` 的业务自助跑数平台，用于让被授权的业务人员在任务中心自助触发数据处理任务，并让管理员统一维护任务配置、授权范围、执行规则和执行记录。

平台当前分为三类数据或外部调用：

- 平台数据库：存放平台自身配置和记录，例如管理员、目录、任务配置、授权关系、DS 下拉选项、执行记录和审计日志。
- PG 执行库：仅当任务执行方式为 `PG 存储过程` 时连接，用于调用指定 PostgreSQL 数据库中的存储过程或后置方法。
- DolphinScheduler：仅当任务执行方式为 `DS 工作流` 时调用接口，用于启动并轮询 DS 流程实例。

## 技术栈

- 后端：FastAPI、SQLAlchemy、Pydantic Settings、psycopg2、python-jose。
- 前端：Vue 3、Vue Router、Pinia、Element Plus、Axios、Vite、TypeScript。
- 数据库：PostgreSQL。
- 部署参考：`deploy/backend.service.example`、`deploy/nginx.conf.example`。

## 项目结构

```text
backend/
  app/
    api/              # FastAPI 路由
    core/             # 配置与安全
    db/               # 数据库连接、schema 与运行期补齐
    models/           # SQLAlchemy 模型
    schemas/          # Pydantic 入参/出参模型
    services/         # 任务、执行、人员、DS、PG 调用等业务逻辑
  tests/              # 后端单元测试
  .env.example        # 后端配置模板
frontend/
  src/
    views/            # 任务中心、管理后台
    router/           # 前端路由与 URL 登录跳转
    stores/           # 登录态
    api/              # Axios 实例
deploy/               # systemd 与 nginx 示例
docs/                 # 架构说明
```

## 主要功能

- 任务中心：普通用户查看自己可见或可执行的任务，执行有权限的任务，查看自己的执行记录。
- 管理后台：管理员维护目录、任务配置、执行方式、授权人员、通知人员、测试状态、发布状态和任务中心展示状态。
- 目录模块：支持根目录下创建二级目录，二级目录下创建三级目录，最多三级。
- 双执行方式：支持 `DS 工作流` 和 `PG 存储过程`。
- 权限控制：
  - 用户在“可执行人员”中：可见并可执行任务。
  - 用户在“可见人员”中：可见任务，但不可执行。
  - 外部人员视图中的用户均按普通用户处理。
  - 平台库 `sys_admin_user` 中配置的用户拥有管理员权限。
- 执行限制：
  - 支持按“用户允许执行时间”配置 5 段 Cron 表达式。
  - 支持重复触发拦截窗口。同一个任务在窗口期内存在 `PENDING/RUNNING` 记录时，会拦截重复执行；`SUCCEEDED/FAILED` 不拦截。
- 执行记录和审计日志持久化到平台记录 schema。

## 登录与访问

前端没有独立登录页，使用 URL 参数登录：

```text
http://localhost:5173/?user=fine_manager
http://localhost:5173/?user=普通用户名或邮箱
```

后端登录接口只根据 `user` 参数识别身份，不校验密码：

- 用户名或 email 存在于外部人员视图：进入任务中心，视为普通用户。
- 用户名存在于平台库 `sys_admin_user`：进入管理后台，视为管理员。
- `fine_manager` 会自动作为管理员用户处理。

前端登录成功后会保存 Bearer Token，并根据角色跳转：

- 管理员：`/admin/tasks`
- 普通用户：`/tasks`

后端 API 前缀默认为 `/api/v1`，健康检查接口为：

```text
GET /health
```

OpenAPI 地址为：

```text
/api/v1/openapi.json
```

## 本地启动

### 后端

首次部署时，可以参考 `.env.example` 创建真实配置文件：

```powershell
cd E:\WorkFile\VSCodeProject\Self-service-Running-Data-Platform\backend
Copy-Item .env.example .env
```

实际配置只维护在 `backend/.env` 中，`.env.example` 只是模板说明文件。

安装依赖并启动：

```powershell
cd E:\WorkFile\VSCodeProject\Self-service-Running-Data-Platform\backend
D:/Anaconda_envs/envs/py311_ai/python.exe -m pip install -r requirements.txt
D:/Anaconda_envs/envs/py311_ai/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

也可以使用脚本：

```powershell
cd E:\WorkFile\VSCodeProject\Self-service-Running-Data-Platform\backend
.\scripts\start.ps1
```

后端启动时会：

- 创建 `PLATFORM_CONFIG_SCHEMA` 和 `PLATFORM_RECORD_SCHEMA`。
- 执行 SQLAlchemy `create_all` 创建缺失表。
- 执行运行期兼容逻辑，补齐当前代码需要的缺失字段或索引。
- 初始化默认目录、DS 元数据下拉项和默认管理员 `admin`。

### 前端

```powershell
cd E:\WorkFile\VSCodeProject\Self-service-Running-Data-Platform\frontend
npm.cmd install
npm.cmd run dev
```

前端开发服务默认监听 `5173`，并将 `/api` 代理到 `http://127.0.0.1:8000`。

生产构建：

```powershell
cd E:\WorkFile\VSCodeProject\Self-service-Running-Data-Platform\frontend
npm.cmd run build
```

## 环境配置

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

平台数据只使用 PostgreSQL 平台库。

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

- `PLATFORM_CONFIG_SCHEMA`：存任务、目录、管理员、任务授权 email、DS 元数据下拉项等配置类表。
- `PLATFORM_RECORD_SCHEMA`：存任务执行记录、审计日志等记录类表。

### 外部人员视图

管理后台任务配置中的“可见人员”“可执行人员”“失败联系人”候选项来自外部 PostgreSQL 数据库中的人员视图。

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

注意：

- `REPORT_USER_SCHEMA` 是外部人员视图所在 schema，连接外部人员视图数据库时统一从这里读取 schema。
- `REPORT_USER_VIEW_NAME` 只能填写视图名，不要包含 schema。
- `REPORT_USER_EMAIL_COLUMN` 是稳定用户标识，任务授权、执行记录和审计记录都保存规范化后的 email。
- 前端人员选项展示为 `fullname(email)`。

### PG 存储过程执行库

仅当任务执行方式为 `PG 存储过程` 时使用：

```env
PG_EXECUTION_HOST=127.0.0.1
PG_EXECUTION_PORT=5432
PG_EXECUTION_DATABASE=postgres
PG_EXECUTION_USERNAME=postgres
PG_EXECUTION_PASSWORD=postgres
PG_EXECUTION_SSLMODE=prefer
TASK_DEFAULT_DS_CALLBACK_METHOD=SELECT * FROM public.get_user_rank(:job_instance_name) ;
TASK_DEFAULT_PG_CALLBACK_METHOD=SELECT * FROM public.get_user_rank(:job_instance_name) ;
```

任务配置中“存储过程”必须填写 `CALL` 语句，可以填写多条，分隔符只支持英文分号 `;`。

```sql
call public.p_new_time(:job_instance_name); call public.p_sync_data();
```

`:job_instance_name` 是可选占位符。执行时会由任务名称拼接 17 位时间戳生成实例名，例如 `多任务-20260506214618336`，并替换到 SQL 中。

`TASK_DEFAULT_DS_CALLBACK_METHOD` 和 `TASK_DEFAULT_PG_CALLBACK_METHOD` 用于管理后台新建任务时预填“后置方法”，可以留空。它们只影响新建任务的默认表单值，不会覆盖已有任务配置。

PG 后置方法可以不填；如果填写，必须是一条包含 `:job_instance_name` 的 `SELECT` 语句，例如：

```sql
SELECT * FROM public.get_user_rank(:job_instance_name);
```

后置方法返回结果为空时算成功；如果返回结果不为空，会把返回结果作为失败信息输出。

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
```

环境变量未配置时请保持等号后为空，注释请单独写一行；后端会把空值或以 `#` 开头的配置值视为未配置，不会把注释内容当作默认值。

管理后台任务配置中：

- `流程定义编码`：对应 DS process definition code。
- `startParams(JSON)`：可选，必须是 JSON 对象。
- `projectCode`：下拉框展示 `ds_project.name`，调用时使用 `ds_project.code`。也可由 `DOLPHINSCHEDULER_PROJECT_CODE` 提供默认值。
- `environmentCode`：下拉框展示 `ds_environment.name`，调用时使用 `ds_environment.code`。
- `warningGroupId`：下拉框展示 `ds_alertgroup.group_name`，调用时使用 `ds_alertgroup.id`。
- `workerGroup`、`failureStrategy`、`processInstancePriority`、`warningType`、`execType` 使用任务参数或环境配置默认值。
- 新建 DS 任务时，管理后台会从 `DOLPHINSCHEDULER_PROJECT_CODE`、`DOLPHINSCHEDULER_WORKER_GROUP`、`DOLPHINSCHEDULER_FAILURE_STRATEGY`、`DOLPHINSCHEDULER_PROCESS_INSTANCE_PRIORITY`、`DOLPHINSCHEDULER_WARNING_TYPE`、`DOLPHINSCHEDULER_EXEC_TYPE`、`DOLPHINSCHEDULER_ENVIRONMENT_CODE`、`DOLPHINSCHEDULER_WARNING_GROUP_ID` 读取默认表单值。
- `后置方法`：可不填。填写时在 DS 流程成功后调用 PG 执行库中的 PostgreSQL 方法，必须包含 `:job_instance_name` 占位符。新建任务的默认值来自 `TASK_DEFAULT_DS_CALLBACK_METHOD`。

## 数据表与初始化

平台启动时按 schema 分区维护数据：

`PLATFORM_CONFIG_SCHEMA`：

- `sys_admin_user`：管理员账号。
- `dr_task_directory`：任务目录。
- `dr_task_definition`：任务定义、执行配置、测试状态、发布状态和任务中心状态。
- `dr_task_visible_user`：可见人员授权关系。
- `dr_task_execute_user`：可执行人员授权关系。
- `dr_task_notify_user`：失败联系人关系。
- `ds_project`、`ds_environment`、`ds_alertgroup`：DS 下拉选项元数据。

`PLATFORM_RECORD_SCHEMA`：

- `dr_task_execution`：任务执行记录。
- `dr_audit_log`：管理操作和系统初始化审计日志。

默认初始化内容：

- 目录：`物流`、`财务`、`供应链`。
- 管理员：`admin`。
- DS 元数据：若对应表为空，会插入内置示例项目、环境和告警组。

## 任务配置与发布规则

任务保存后会进入“已配置任务”，但不会自动出现在任务中心。

发布到任务中心的基本流程：

1. 管理员在管理后台配置任务。
2. 执行测试。
3. 当前执行配置测试成功后发布任务。
4. 在任务中心通过“添加任务”把任务加入任务中心。

执行相关配置变化后，旧测试结果会失效，需要重新测试后才能发布。

执行相关配置包括：

- DS 工作流：执行方式、流程定义编码、projectCode、failureStrategy、processInstancePriority、warningType、workerGroup、execType、startParams、environmentCode、warningGroupId、后置方法。
- PG 存储过程：执行方式、存储过程、后置方法。

非执行配置变化时，不会清空已有测试状态和发布状态，例如目录、失败联系人、可见人员、可执行人员、影响范围、执行前提、重复触发窗口、用户允许执行时间等。

删除“已配置任务”中的任务会删除该任务配置、测试结果、关联执行记录以及任务中心中的对应按钮，并重新整理后续任务编码。

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
- `POST /admin/tasks/{task_id}/add-to-center`：添加到任务中心。
- `POST /admin/tasks/{task_id}/remove-from-center`：从任务中心移除。
- `POST /admin/tasks/test-execution`：测试任务执行配置。
- `GET /admin/task-directories`、`POST /admin/task-directories`、`PUT /admin/task-directories/{directory_id}`、`DELETE /admin/task-directories/{directory_id}`：目录管理。
- `GET /admin/users`：获取外部人员候选项。
- `GET /admin/executions`：管理员查看全部执行记录。
- `GET /admin/ds-config`：获取 DS 默认配置。
- `GET /admin/ds-options`：获取 DS 下拉选项。
- `GET /dashboard/summary`：平台看板摘要。

## 测试与检查

后端单元测试：

```powershell
cd E:\WorkFile\VSCodeProject\Self-service-Running-Data-Platform\backend
D:/Anaconda_envs/envs/py311_ai/python.exe -m unittest tests.test_task_code_rules tests.test_dolphinscheduler_instance_selection
```

前端构建：

```powershell
cd E:\WorkFile\VSCodeProject\Self-service-Running-Data-Platform\frontend
npm.cmd run build
```

## 部署参考

后端 systemd 示例：

```text
deploy/backend.service.example
```

前端构建产物默认在：

```text
frontend/dist
```

nginx 示例会将静态资源指向 `frontend/dist`，并将 `/api/` 反向代理到 `http://127.0.0.1:8000/api/`：

```text
deploy/nginx.conf.example
```

## 备注

- `backend/.env` 是真实配置文件，不应提交真实密码或 Token。
- `backend/.env.example` 是配置模板，不存真实密码。
- 后端读取配置时会忽略未声明的额外环境变量。
- 外部人员库、PG 执行库、DolphinScheduler 库与平台库相互独立；平台库只保存平台配置、授权快照、执行记录和审计记录。
