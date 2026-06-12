from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.runtime_schema import ensure_database_schemas, ensure_runtime_schema
from app.db.seed import seed_data
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_database_schemas()
    ensure_runtime_schema()
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
    seed_data()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
