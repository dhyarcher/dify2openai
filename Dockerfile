# ── Stage 1: build dependencies ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

ARG TZ='Asia/Shanghai'

WORKDIR /app

#RUN echo "deb http://deb.debian.org/debian bookworm main\ndeb http://deb.debian.org/debian-security/ bookworm-security main\ndeb http://deb.debian.org/debian bookworm-updates main" > /etc/apt/sources.list

# 执行替换（将官方源替换为清华源）
#RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
# 这些库能让 numpy/pandas 快速编译通过
#RUN apt-get update && apt-get install -y --no-install-recommends \
#    build-essential \
#    gcc \
#    g++ \
#    && rm -rf /var/lib/apt/lists/*
# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv -i https://mirrors.aliyun.com/pypi/simple/

# Copy dependency manifests first (layer-cache friendly)
COPY pyproject.toml uv.lock ./

# Install deps into a separate prefix so we can copy just them
RUN UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ uv sync --frozen --no-dev --no-install-project


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Security: run as non-root
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /app/.venv /app/.venv

COPY . .

# Make venv the active python
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN chmod +x /app/*

USER root

EXPOSE 8000

# Production: no --reload, multiple workers via uvicorn
CMD ["uvicorn", "app:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "4", \
    "--no-access-log"]
