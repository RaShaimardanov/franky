# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


FROM python:3.13-slim

# ffmpeg — для сжатия выпусков больше лимита Bot API (`franky compress`).
RUN apt-get update     && apt-get install -y --no-install-recommends ffmpeg     && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 franky
WORKDIR /app
COPY --from=builder --chown=franky:franky /app/.venv /app/.venv
COPY --chown=franky:franky alembic.ini ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    LOG_JSON=true

RUN mkdir -p /app/data/audio && chown franky:franky /app/data/audio
USER franky

CMD ["franky", "bot"]
