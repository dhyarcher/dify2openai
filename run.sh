#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# run.sh — Start the dify2openai service with uvicorn.
#
# Configurable via environment variables:
#   HOST       Bind host           (default: 0.0.0.0)
#   PORT       Bind port           (default: 8000)
#   WORKERS    Number of workers   (default: 1)
#   LOG_LEVEL  Uvicorn log level   (default: info)
#   RELOAD     Enable hot-reload   (default: false) — dev mode, overrides WORKERS
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"
LOG_LEVEL="${LOG_LEVEL:-info}"
RELOAD="${RELOAD:-false}"

echo "Starting dify2openai service..."
echo "  Host      : ${HOST}"
echo "  Port      : ${PORT}"
echo "  Log level : ${LOG_LEVEL}"

if [ "${RELOAD}" = "true" ]; then
    echo "  Mode      : development (--reload)"
    exec uvicorn app:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --log-level "${LOG_LEVEL}" \
        --reload
else
    echo "  Workers   : ${WORKERS}"
    echo "  Mode      : production"
    exec uvicorn app:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --workers "${WORKERS}" \
        --log-level "${LOG_LEVEL}" \
        --no-access-log
fi
