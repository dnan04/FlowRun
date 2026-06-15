# syntax=docker/dockerfile:1

FROM docker.m.daocloud.io/library/node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
# 优化 1：使用国内淘宝 npm 镜像源加速下载
RUN npm config set registry https://registry.npmmirror.com \
    && npm ci

COPY frontend/ ./
RUN npm run build


# 2. 修改后端运行基础镜像
FROM docker.m.daocloud.io/library/python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BACKEND_HOST=127.0.0.1 \
    BACKEND_PORT=8000

WORKDIR /app

# 优化 2：将 Debian 官方源替换为阿里云镜像源，解决 apt-get 卡死问题
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
    || sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

COPY backend/requirements.txt /app/backend/requirements.txt
# 优化 3：使用阿里云 pip 镜像源加速 Python 依赖包下载
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -i https://mirrors.aliyun.com/pypi/simple/ -r /app/backend/requirements.txt

COPY backend/app /app/backend/app
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/start.sh /app/start.sh

RUN chmod +x /app/start.sh \
    && mkdir -p /var/cache/nginx /var/run/nginx

WORKDIR /app/backend

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1/health', timeout=3).read()" || exit 1

CMD ["/app/start.sh"]
