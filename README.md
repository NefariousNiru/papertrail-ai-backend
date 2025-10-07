# 🧰 Backend – README.md

## PaperTrail AI — FastAPI Backend

### What problem does this solve?

Academic writing is full of factual claims that may be **uncited**, **weakly cited**, or improperly supported. Manual verification is slow and error-prone. PaperTrail AI verifies whether claims in a paper are supported by the cited sources—**semantically**, not just by keyword matching.

### Goals

* Extract factual claims from a paper and classify them (cited / uncited / weakly cited).
* Verify claims against their cited sources using semantic retrieval + LLM reasoning.
* Provide **live, streaming** feedback to the UI.
* Keep the system private and lightweight: **no long-term storage**, no auth.
* Persist only what’s needed for a great UX (short-lived): **2h TTL in Redis**.

---

## High-level architecture

```
FastAPI (ASGI)
  ├─ Redis (2h TTL) for ephemeral state
  │   ├─ JobRepository            # job metadata, TTL refresh while active
  │   ├─ ClaimBufferRepository    # append-only list of streamed claims per job
  │   └─ VerificationRepository   # per-(jobId, claimId) verification result (verdict, confidence, reasoning, evidence[])
  ├─ (Planned) PyMuPDF            # page-aware text extraction
  ├─ (Planned) FAISS (in-memory)  # per-paper semantic search indices
  ├─ (Planned) Semantic Scholar   # suggestions for uncited claims
  └─ Anthropic Claude (validate; later: verify prompts)
```

**Design choices**

* **Ephemeral by default**: No accounts, no durable DB. Jobs live in Redis for 2 hours.
* **Privacy**: API keys are never stored. Request bodies are not logged.
* **Resilience**: If the user refreshes the page, previously streamed claims are **replayed** from Redis, and verified claims are **merged** with their saved verdict/evidence.

---

## What’s implemented (MVP core)

* ✅ **FastAPI project skeleton** with CORS and graceful lifespan.
* ✅ **Redis integration** (`config/cache.py`) with warm-up on startup and clean shutdown.
* ✅ **JobRepository** (2h TTL) to hold basic job metadata (`id`, `status`, etc.).
* ✅ **ClaimBufferRepository** to store already-emitted claims for **replay after refresh**.
* ✅ **VerificationRepository** to **persist verification results** (verdict, confidence, reasoning, evidence[]) for 2 hours.
* ✅ **NDJSON streaming**: `/api/v1/stream-claim` streams claim events + progress.
* ✅ **Verification persistence**: `/api/v1/verify-claim` saves results; replay merges them.
* ✅ **Evidence support**: Evidence items carry (paperTitle, page, section, paragraph, excerpt) with a **hard cap of 100 words** per excerpt.

> Current verification is a demo stub. The data path is wired; next we’ll plug in FAISS + real prompts.

---

## Endpoints (current)

Base: `/api/v1`

| Method | Path                | Purpose                                             |
| -----: | ------------------- | --------------------------------------------------- |
|   POST | `/validate-api-key` | Pass-through validator (Anthropic ping)             |
|   POST | `/upload-paper`     | Accept a paper file, create `jobId`                 |
|   POST | `/stream-claim`     | **NDJSON** stream of claims+progress                |
|   POST | `/verify-claim`     | Upload cited PDF, return & persist verdict/evidence |

### Request/Response shapes (selected)

**POST `/upload-paper` (multipart)**

* Form fields: `file: File`, `apiKey: string`
* Response: `{ "jobId": "<uuid>" }`

**POST `/stream-claim` (JSON)**

* Body: `{ "jobId": "<uuid>", "apiKey": "<string>" }`
* Response: NDJSON lines, e.g.:

  ```json
  {"type":"claim","payload":{ "id":"c1", "text":"...", "status":"cited", "verdict":"supported" | null, "confidence":0.82 | null, "reasoningMd":"...", "evidence":[{ "paperTitle":"...", "page":3, "section":"Results", "paragraph":2, "excerpt":"(<=100 words)" }] }}
  {"type":"progress","payload":{"processed":5,"total":12}}
  {"type":"done"}
  ```

**POST `/verify-claim` (multipart)**

* Form fields: `jobId: string`, `claimId: string`, `file: File`, `apiKey: string`
* Response:

  ```json
  {
    "claimId":"c1",
    "verdict":"supported" | "partially_supported" | "unsupported",
    "confidence":0.82,
    "reasoningMd":"short explanation",
    "evidence":[{ "paperTitle":"...", "page":3, "section":"Results", "paragraph":2, "excerpt":"(<=100 words)" }]
  }
  ```
* Side effect: The response is **persisted** in Redis for 2 hours; subsequent streams or refreshes reflect the verified state.

---

## Data lifecycle & persistence

* **Job**: `papertrail:jobs:{jobId}` — refreshed while streaming; auto-expires after 2h idle.
* **Claim buffer**: `papertrail:claims:{jobId}` — list of emitted claims so refresh can replay.
* **Verifications**: `papertrail:verifications:{jobId}:{claimId}` — persisted verdict/evidence to merge on replay.

> **Skip** is intentional **front-end only** (ephemeral). We do not persist user choices.

---

## Local setup

**Prereqs**

* Python 3.12+
* Redis 7+ (Docker is fine)

**Install & run API**

```bash
poetry install
poetry run uvicorn main:app --reload --port 8000
```

**Key environment/config**
* `APP_ENV` (default: `dev`)
* `REDIS_URL` (default: `redis://127.0.0.1:6379/0`)
* `ALLOWED_ORIGIN` (e.g., `http://localhost:5173`)
* `ANTHROPIC_MODEL` (e.g., `claude-3-5-sonnet-latest`)
* `ANTHROPIC_API_URL` (`https://api.anthropic.com/v1/messages`)
* `PERSISTENCE_TTL_SECONDS` (`7200` seconds)
---

## Testing quickly

**Health**

```
GET /healthz → { "ok": true }
```

**Validate key**

```
POST /api/v1/validate-api-key
{ "apiKey": "..." }
```

**Upload paper (Postman form-data)**

* `file: <choose a PDF>`
* `apiKey: <your key>`
  → `201 { "jobId": "<uuid>" }`

**Stream (curl for live view)**

```bash
curl -N -H "Content-Type: application/json" \
  -X POST http://127.0.0.1:8000/api/v1/stream-claim \
  -d '{"jobId":"<uuid>","apiKey":"<key>"}'
```

**Verify claim (Postman form-data)**

* `jobId: <uuid>`
* `claimId: c1`
* `file: <cited source PDF>`
* `apiKey: <your key>`

---

## Security & privacy

* **No user accounts; no long-term storage.**
* API keys never saved; pass only in request body; not logged.
* Claims and verification data expire automatically after 2 hours.
* Request/response payloads are sanitized; consider adding PDF scanning in a later hardening pass.

---

## What’s next (backend)

**P1 (immediate)**

1. **Rate limiting + file size/page limits**

   * Per-IP counters via Redis; friendly 429 with `Retry-After`.
   * Enforce max file size/pages and fail fast with 413/422.

2. **Page-based progress**

   * Emit `phase:"parse"` with `processed/total` pages, then extraction totals.
   * Store latest progress snapshot with the job; replay it on reconnect before claims.

3. **Semantic Scholar integration**

   * `/api/v1/suggest-citations` → proxy + cache (Redis TTL 10–30 min); top 3 normalized results.

4. **Core AI pipeline**

   * PyMuPDF text extraction (page-aware), sentence segmentation.
   * Claim detection + citation marker extraction (LLM pass).
   * Per-source: chunk → embed → FAISS (in-memory) → top-k → Claude prompt → verdict + evidence (100-word cap).

5. **Central logging**

   * Structured JSON logs to console + file; include route, jobId, duration, sanitized errors.
   * Strictly avoid logging API keys and document content.

**P2 (soon after)**

* Background job runner (processing continues even if client disconnects).
* Multi-replica readiness (sticky sessions by `jobId` or simple job routing).