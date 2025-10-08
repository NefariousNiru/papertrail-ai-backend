# 🧰 PaperTrail AI — FastAPI Backend

## Overview

Academic writing is filled with factual claims that are **uncited**, **weakly cited**, or **improperly supported**.
Verifying these manually is slow, subjective, and error-prone.

**PaperTrail AI** automates that process. It extracts factual claims from academic papers, classifies them by citation strength, and verifies whether those claims are supported by the cited sources using **semantic similarity** and **LLM-based reasoning**.

This backend is designed to be **private, stateless, and streaming-first** — enabling real-time feedback without storing user data or documents beyond a short runtime window.

---

## 🎯 Core Objectives

* Extract verifiable factual claims from uploaded research papers.
* Detect and label citations as `cited`, `weakly_cited`, or `uncited`.
* Verify each claim against uploaded cited PDFs using **dense embeddings + LLM judgment**.
* Provide **live, streaming NDJSON** output for a responsive frontend.
* Maintain complete privacy — no accounts, no permanent storage, no key retention.

---

## ⚙️ System Architecture

```
                       ┌────────────────────────┐
                       │     Frontend (React)   │
                       │  Uploads PDFs & streams│
                       │   results over NDJSON  │
                       └────────────┬───────────┘
                                    │
                                    ▼
                        ┌──────────────────────┐
                        │   FastAPI Backend    │
                        │  (ASGI + Uvicorn)    │
                        ├──────────────────────┤
                        │ Controller Layer     │
                        │  - paper_controller  │
                        │  - validation_ctrl   │
                        │----------------------│
                        │ Service Layer        │
                        │  - PaperService      │
                        │  - ApiKeyValidation  │
                        │----------------------│
                        │ Core Modules         │
                        │  - pdf_text          │
                        │  - streaming         │
                        │  - verification_pipe │
                        │  - embeddings_retrv  │
                        │----------------------│
                        │ Repository Layer     │
                        │  - jobs / claims /   │
                        │    verifications /   │
                        │    blobs (Redis)     │
                        └─────────┬────────────┘
                                  │
                      ┌───────────┴────────────┐
                      │        Redis 7+        │
                      │  Ephemeral runtime DB  │
                      │  (Job, Claim, Verify)  │
                      └───────────┬────────────┘
                                  │
                                  ▼
                   ┌────────────────────────────┐
                   │   External LLM Provider    │
                   │  (Anthropic Claude 3.5)    │
                   │  Extraction + Verification │
                   └────────────────────────────┘
```

---

## 🧩 Design Principles

| Principle                   | Description                                                                                    |
| --------------------------- | ---------------------------------------------------------------------------------------------- |
| **Ephemeral runtime state** | All jobs, claims, and verifications are stored only for the configured TTL (runtime variable). |
| **Streaming-first**         | Results are streamed via NDJSON for immediate UI feedback.                                     |
| **Replay-safe design**      | Reconnection or refresh replays prior claims and verdicts seamlessly.                          |
| **Privacy by design**       | No persistent storage, no account system, no API key retention.                                |
| **Observability**           | Structured logs with module and line context; sanitized of sensitive data.                     |
| **LLM modularity**          | Embedding model and verifier can be replaced without refactoring.                              |

---

## ✅ Implemented Components

### Core

* **FastAPI ASGI app** with structured routing and graceful lifespan handling.
* **Async Redis integration** (`config/cache.py`) with automatic connection pooling.
* **Repository pattern** for clean separation of job, claim, and verification logic.
* **PyMuPDF-based text extraction** (page-aware, low-memory).
* **Sentence-Transformers** embeddings for semantic verification.
* **Anthropic Claude** LLMs for both claim extraction and verification passes.
* **NDJSON streaming** of live claim extraction results.
* **Verification persistence** with replay merging (user refresh-safe).

### Services

* `PaperService`: orchestrates extraction, buffering, verification, and replay.
* `ApiKeyValidationService`: pings Anthropic to verify the provided key.

### Utilities

* `util.logger`: structured, colored logging with module origin and timestamp.
* `util.errors`: unified exception handling (AppError class).
* `util.timing`: lightweight timing context manager for profiling.

---

## 🧠 Data Model & Lifecycle

| Key                                          | Description                                   | TTL                                        |
| -------------------------------------------- | --------------------------------------------- | ------------------------------------------ |
| `papertrail:jobs:{jobId}`                    | Metadata & progress snapshot for each job     | Configurable via `PERSISTENCE_TTL_SECONDS` |
| `papertrail:claims:{jobId}`                  | Ordered buffer of emitted claims (for replay) | Configurable                               |
| `papertrail:verifications:{jobId}:{claimId}` | Persisted verdict and evidence                | Configurable                               |

* Each Redis key auto-expires after the runtime-configured TTL.
* TTL is refreshed during active streaming or verification to extend session life.
* When clients reconnect, prior data are **replayed automatically** to restore state.

---

## 🚀 API Endpoints

**Base:** `/api/v1`

| Method | Path                | Description                                   |
| :----: | :------------------ | :-------------------------------------------- |
| `POST` | `/validate-api-key` | Validate Anthropic key                        |
| `POST` | `/upload-paper`     | Upload a research paper and start a job       |
| `POST` | `/stream-claim`     | Stream extracted claims and progress (NDJSON) |
| `POST` | `/verify-claim`     | Verify one claim against its cited source     |

---

### Example Flows

#### 1. Upload Paper

```bash
curl -X POST http://127.0.0.1:8000/api/v1/upload-paper \
  -F "file=@paper.pdf" \
  -F "apiKey=<anthropic-key>"
```

Response:

```json
{ "jobId": "9e21b9c3-7de4-4a09-8151-d772bd3c8f20" }
```

#### 2. Stream Claims

```bash
curl -N -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/v1/stream-claim \
  -d '{"jobId":"9e21b9c3-7de4-4a09-8151-d772bd3c8f20","apiKey":"<key>"}'
```

NDJSON stream:

```json
{"type":"progress","payload":{"phase":"extract","processed":3,"total":10}}
{"type":"claim","payload":{"id":"c1","text":"As noted by Zhao et al. (2020), transformer layers improve contextual encoding.","status":"cited"}}
{"type":"claim","payload":{"id":"c2","text":"Previous work suggests similar improvements without attention layers.","status":"weakly_cited","weak_reason":"mentions prior work without explicit reference"}}
{"type":"done"}
```

#### 3. Verify Claim

```bash
curl -X POST http://127.0.0.1:8000/api/v1/verify-claim \
  -F "jobId=9e21b9c3-7de4-4a09-8151-d772bd3c8f20" \
  -F "claimId=c1" \
  -F "file=@cited_source.pdf" \
  -F "apiKey=<anthropic-key>"
```

Response:

```json
{
  "claimId": "c1",
  "verdict": "supported",
  "confidence": 0.91,
  "reasoningMd": "The cited paper explicitly demonstrates transformer-based improvements under comparable conditions.",
  "evidence": [
    {
      "paperTitle": "Attention is All You Need",
      "page": 3,
      "section": "Experiments",
      "paragraph": 2,
      "excerpt": "Transformers outperform RNNs on language modeling tasks..."
    }
  ]
}
```

---

## 🧾 Implementation Notes

* **Idempotent streaming**: multiple `/stream-claim` calls replay the same data safely.
* **Merge logic**: verified claims update existing entries without duplication.
* **Error handling**: all raised `AppError` objects map to clear HTTP responses.
* **Concurrency**: PDF parsing, LLM calls, and Redis operations run fully asynchronously.
* **Configurable runtime TTL**: controlled via `PERSISTENCE_TTL_SECONDS` env var.
* **Strict logging discipline**:

  * No API keys or content logged.
  * Each log includes `timestamp`, `level`, `file:line`, and message.

---

## 🔧 Local Setup

### Prerequisites

* Python 3.12+
* Redis 7+
* Poetry

### Run locally

```bash
poetry install
poetry run uvicorn main:app --reload --port 8000
```

### Key Environment Variables

| Variable                  | Default                                 | Description                              |
| ------------------------- | --------------------------------------- | ---------------------------------------- |
| `APP_ENV`                 | `dev`                                   | Environment flag                         |
| `REDIS_URL`               | `redis://127.0.0.1:6379/0`              | Redis connection                         |
| `ALLOWED_ORIGIN`          | `http://localhost:5173`                 | CORS frontend origin                     |
| `ANTHROPIC_MODEL`         | `claude-3-5-sonnet-latest`              | Model used for extraction + verification |
| `ANTHROPIC_API_URL`       | `https://api.anthropic.com/v1/messages` | Anthropic endpoint                       |
| `PERSISTENCE_TTL_SECONDS` | `7200`                                  | Time-to-live for ephemeral runtime data  |

---

## 🧰 Coding Standards

* **PEP8 + Black** formatting
* **Type-annotated** throughout
* **Repository-Service separation** for clean layering
* **Single-responsibility modules** (`core/`, `service/`, `repository/`)
* **Structured JSON logs** with module-level `_log` instances
* **Graceful startup/shutdown** via FastAPI lifespan events
* **Strict NDJSON compliance** for streaming endpoints

---

## 🔐 Security & Privacy

* No persistent storage (TTL-controlled runtime only)
* No user accounts or authentication
* No API key or PDF content persisted or logged
* Logs sanitized before emission
* Future hardening:

  * File size/page limit enforcement
  * Per-IP rate limiting via Redis counters

---

## 🧱 Deployment

### Docker Example

```dockerfile
FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry==1.8.3 \
  && poetry export -f requirements.txt --without-hashes -o requirements.txt \
  && pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
```

### Deployment Notes

* Works on **Railway**, **Fly.io**, **Render**, or any Docker-compatible host.
* Attach a managed Redis instance.
* Supply environment variables (including Anthropic API key) via deployment settings.
* The Redis TTL determines data persistence window automatically.

---

## 🧩 Testing & Verification

```bash
# Run local API
poetry run uvicorn main:app --reload

# Health check
curl http://127.0.0.1:8000/healthz

# Quick verification
pytest tests/
```

*Integration tests validate:*

* NDJSON parsing
* Redis persistence
* LLM response schema
* Claim replay after refresh

---

## 🧾 License

**MIT License © 2025 NefariousNiru**