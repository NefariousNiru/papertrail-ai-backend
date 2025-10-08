# ---------- Runtime image ----------
FROM python:3.12-slim
WORKDIR /app

# Minimal runtime libs for PyMuPDF on slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libxrender1 libxext6 libsm6 \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=prod

# Create requirements.txt straight from your pyproject versions
# (matches [tool.poetry.dependencies])
RUN printf '%s\n' \
  'fastapi==0.118.0' \
  'httpx==0.28.1' \
  'uvicorn==0.37.0' \
  'pydantic==2.11.10' \
  'python-multipart==0.0.20' \
  'pydantic-settings==2.11.0' \
  'python-dotenv==1.1.1' \
  'redis==6.4.0' \
  'fastapi-limiter==0.1.6' \
  'pymupdf==1.26.4' \
  'numpy==2.3.3' \
  'sentence-transformers==5.1.1' \
  > requirements.txt

# Install deps (CPU wheels for sentence-transformers/torch will be pulled automatically)
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Honour Railway's $PORT, default to 8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips '*'"]
