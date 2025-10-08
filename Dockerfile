# ---------- Builder: export requirements from Poetry ----------
FROM python:3.12-slim AS build
WORKDIR /app
RUN pip install --no-cache-dir poetry==1.8.3
COPY pyproject.toml poetry.lock* ./
RUN poetry export -f requirements.txt --without-hashes -o requirements.txt

# ---------- Runtime image ----------
FROM python:3.12-slim
WORKDIR /app

# Minimal runtime libs needed by PyMuPDF on slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libxrender1 libxext6 libsm6 \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=prod

COPY --from=build /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Railway sets $PORT; fallback to 8000 for local
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
