# syntax=docker/dockerfile:1

# ---- Base builder ----
FROM python:3.12-slim AS builder

# Set working dir
WORKDIR /app

# System deps for PyMuPDF + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libglib2.0-0 libxrender1 libxext6 libsm6 \
    && rm -rf /var/lib/apt/lists/*

# Copy Poetry setup first (for caching)
COPY pyproject.toml poetry.lock* poetry.toml* ./

# Install Poetry (no virtualenv inside container)
RUN pip install --no-cache-dir poetry \
 && poetry config virtualenvs.create false \
 && poetry install --only main --no-root --no-interaction --no-ansi

# ---- Runtime image ----
FROM python:3.12-slim

WORKDIR /app

# Copy runtime system libs (same as builder)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libxrender1 libxext6 libsm6 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed site-packages from builder
COPY --from=builder /usr/local /usr/local

# Copy the source code
COPY . .

# Environment defaults (can be overridden)
ENV APP_ENV=prod \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose port for FastAPI
EXPOSE 8080

# Start the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
