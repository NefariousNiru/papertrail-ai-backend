# config/settings.py
import os
import sys
from dotenv import load_dotenv
from pydantic import ValidationError, Field
from pydantic_settings import BaseSettings
from util.enums import Environment


if os.getenv("APP_ENV", Environment.DEV) == Environment.DEV:
    load_dotenv()


class Settings(BaseSettings):
    # App
    APP_ENV: str = Field(..., validation_alias="APP_ENV")
    REDIS_URL: str = Field(..., validation_alias="REDIS_URL")
    PERSISTENCE_TTL_SECONDS: str = Field(
        ..., validation_alias="PERSISTENCE_TTL_SECONDS"
    )

    # CORS & Limits
    ALLOWED_ORIGIN: str = Field(..., validation_alias="ALLOWED_ORIGIN")
    RATE_LIMIT_TIMES: str = Field(..., validation_alias="RATE_LIMIT_TIMES")
    RATE_LIMIT_SECONDS: int = Field(..., validation_alias="RATE_LIMIT_SECONDS")
    MAX_FILE_MB: int = Field(..., validation_alias="MAX_FILE_MB")
    TRUST_PROXY: bool = Field(..., validation_alias="TRUST_PROXY")

    # Anthropic Settings
    ANTHROPIC_API_URL: str = Field(..., validation_alias="ANTHROPIC_API_URL")
    ANTHROPIC_MODEL: str = Field(..., validation_alias="ANTHROPIC_MODEL")
    ANTHROPIC_VERSION: str = Field(..., validation_alias="ANTHROPIC_VERSION")

    # Embedding Engine
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EXTRACT_CONCURRENCY: int = 4

    # Prompts
    EXTRACT_SYSTEM_PROMPT: str = (
        "You extract concise factual claims from academic text and research papers.\n"
        "Output format:\n"
        "- Return NDJSON: one JSON object per line (no surrounding array).\n"
        '- Each line must be: {"id":"<unique>","text":"...","status":"cited|weakly_cited|uncited"}\n'
        "- Emit AT MOST 8 lines per request.\n"
        "- No extra prose. No code fences.\n"
        "\n"
        "Guidelines:\n"
        "- Extract only checkable factual statements under 280 chars.\n"
        '- status: "cited" if a citation marker like [12] or (Smith, 2020) appears; "weakly_cited" if ambiguous; else "uncited".\n'
    )

    VERIFY_SYSTEM_PROMPT: str = (
        "You are a careful scientific fact-checker. Given a CLAIM and EVIDENCE EXCERPTS from a cited paper, decide if the evidence SUPPORTS the claim, PARTIALLY SUPPORTS it, or is UNSUPPORTED.\n\n"
        "Rules:\n"
        "- Judge only based on provided excerpts.\n"
        "- If evidence is mixed or partial, choose PARTIALLY_SUPPORTED.\n"
        "- Keep the explanation short (markdown ok).\n"
        '- Return JSON only: {"verdict": "...", "confidence": 0.0-1.0, "reasoningMd":"..." }.\n'
        '- verdict ∈ {"supported","partially_supported","unsupported"}.\n'
        "- No code fences.\n"
    )


try:
    settings = Settings()
except ValidationError as e:
    print("❌ Missing/invalid environment variables:", file=sys.stderr)
    for err in e.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "")
        print(f" - {loc}: {msg}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"❌ Settings initialization failed: {e}", file=sys.stderr)
    sys.exit(1)
