from fastapi import APIRouter

from app.api.routes import admin, auth, dashboard, tasks

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["业务任务"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理后台"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["平台看板"])
