from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

platform_url = settings.platform_sqlalchemy_url
if not platform_url:
    raise RuntimeError("平台数据库配置缺失，请在 .env 中配置 PLATFORM_DB_*。")

engine = create_engine(platform_url)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
