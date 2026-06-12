#!/usr/bin/env sh
set -eu

uvicorn app.main:app --host "${BACKEND_HOST:-127.0.0.1}" --port "${BACKEND_PORT:-8000}" &
backend_pid="$!"

nginx -g "daemon off;" &
nginx_pid="$!"

shutdown() {
    kill -TERM "$backend_pid" "$nginx_pid" 2>/dev/null || true
    wait "$backend_pid" "$nginx_pid" 2>/dev/null || true
}

trap shutdown INT TERM

while :; do
    if ! kill -0 "$backend_pid" 2>/dev/null; then
        status=0
        wait "$backend_pid" || status="$?"
        kill -TERM "$nginx_pid" 2>/dev/null || true
        wait "$nginx_pid" 2>/dev/null || true
        exit "$status"
    fi
    if ! kill -0 "$nginx_pid" 2>/dev/null; then
        status=0
        wait "$nginx_pid" || status="$?"
        kill -TERM "$backend_pid" 2>/dev/null || true
        wait "$backend_pid" 2>/dev/null || true
        exit "$status"
    fi
    sleep 1
done
