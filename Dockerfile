# syntax=docker/dockerfile:1.6
#
# Multi-stage build:
#   stage 1 — node : builds the React frontend (Vite → static assets)
#   stage 2 — python: installs backend deps, pre-downloads the embedding
#                    model, copies the built frontend, runs FastAPI.
#
# Final image is self-contained: FastAPI serves both /api/* and the SPA.
# Tuned for Hugging Face Spaces (Docker SDK) — listens on port 7860 and
# runs as the non-root `user` (UID 1000) HF Spaces convention.

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Frontend build
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /build

# Cache layer: deps before sources
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build
# → /build/dist


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Backend + static
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Non-root user (HF Spaces convention)
RUN useradd --create-home --uid 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/user/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/home/user/.cache/sentence_transformers \
    STATIC_DIR=/home/user/app/static

WORKDIR $HOME/app

# Install CPU-only torch first (saves ~500 MB vs the default CUDA wheel)
RUN pip install --user --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch

# Backend dependencies
COPY --chown=user backend/requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

# Pre-download the embedding model so the first request is instant
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Backend source
COPY --chown=user backend/ ./backend/

# Built frontend (served as static)
COPY --chown=user --from=frontend-build /build/dist ./static/

# HF Spaces default port
EXPOSE 7860

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
