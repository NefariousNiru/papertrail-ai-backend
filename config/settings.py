# config/settings.py
import os
import sys
from dotenv import load_dotenv
from pydantic import ValidationError, Field
from pydantic_settings import BaseSettings
from util.enums import Environment
import logging


if os.getenv("APP_ENV", Environment.DEV) == Environment.DEV:
    load_dotenv()

_log = logging.getLogger("config.settings")


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

    # External URLS:
    SEMANTIC_SEARCH_URL: str = "https://api.semanticscholar.org/graph/v1/paper/search"

    # Anthropic Settings
    ANTHROPIC_API_URL: str = Field(..., validation_alias="ANTHROPIC_API_URL")
    ANTHROPIC_MODEL: str = Field(..., validation_alias="ANTHROPIC_MODEL")
    ANTHROPIC_VERSION: str = Field(..., validation_alias="ANTHROPIC_VERSION")

    # Embedding Engine
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EXTRACT_CONCURRENCY: int = 4

    # Logging knobs
    LOGGER_NAME: str = "paper-trail-ai"
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    LOG_TO_FILE: bool = Field(default=False, validation_alias="LOG_TO_FILE")
    LOG_DIR: str = Field(default="logs", validation_alias="LOG_DIR")
    LOG_FILE_NAME: str = Field(default="app.log", validation_alias="LOG_FILE_NAME")
    LOG_MAX_BYTES: int = Field(
        default=50 * 1024 * 1024, validation_alias="LOG_MAX_BYTES"
    )
    LOG_BACKUP_COUNT: int = Field(default=5, validation_alias="LOG_BACKUP_COUNT")

    # Prompts
    EXTRACT_SYSTEM_PROMPT: str = (
        "You extract only high-signal, checkable factual CLAIMS that this paper makes "
        "ABOUT EXTERNAL WORK (third-party claims). Ignore claims about THIS paper’s own methods, results, or conclusions.\n"
        "\n"
        "OUTPUT (NDJSON): One JSON object per line. No arrays. No code fences.\n"
        'Each line MUST include: {"id":"<unique>","text":"<verbatim sentence>","status":"cited|weakly_cited|uncited"}\n'
        'Optional when status == "weakly_cited": add "weak_reason":"<short reason why ambiguous>"\n'
        "\n"
        "STRICT TEXT RULES:\n"
        '- The value of "text" MUST be a VERBATIM copy of a single sentence from the provided page (original punctuation/case).\n'
        "- If the sentence contains inline citation marker(s), KEEP THEM in the text exactly as printed (e.g., [12], (Smith, 2020)).\n"
        "- Do NOT paraphrase, merge sentences, or add commentary to the text.\n"
        "\n"
        "WHAT TO EXTRACT:\n"
        "- Only sentences that attribute facts to third parties (e.g., “As Smith (2019) showed…”, “According to CDC (2021)…”, "
        "“Prior work demonstrates… [12]”).\n"
        "- Prefer quality over quantity. Emit claims only when the statement plausibly requires citation "
        "(non-trivial, not common knowledge in a general sense).\n"
        "- No hard limit on the number of lines; emit as many as meet the criteria for this page, possibly zero.\n"
        "\n"
        "STATUS RULES:\n"
        '- Use "cited" when the sentence includes an explicit inline citation marker (e.g., [7], (Jones, 2020), superscript refs). '
        'These markers MUST remain in the verbatim text so the claim appears as "<sentence> [7]".\n'
        '- Use "weakly_cited" when attribution is implied but no explicit marker is present (e.g., “previous studies suggest”, '
        '“prior work has shown”). In this case, include a short "weak_reason" explaining the ambiguity (e.g., '
        '"generic phrase without explicit reference", "mentions author without year", etc.).\n'
        '- Use "uncited" when there is no attribution and the sentence nonetheless reads like a factual claim that would'
        "benefit from a source.\n"
        "\n"
        "GENERAL:\n"
        "- Do not include claims about this paper itself (methods, experiments, dataset sizes, its own results, or conclusions).\n"
        "- No extra prose or explanations outside the NDJSON objects.\n"
    )

    VERIFY_SYSTEM_PROMPT: str = (
        "You are a careful scientific fact-checker. Given a CLAIM and EVIDENCE EXCERPTS from the cited paper, decide if the evidence "
        "SUPPORTS the claim, PARTIALLY SUPPORTS it, or is UNSUPPORTED.\n\n"
        "Rules:\n"
        "- Judge ONLY from the provided excerpts; do not assume context outside them.\n"
        "- If evidence is mixed, tangential, or insufficient, choose PARTIALLY_SUPPORTED (not supported).\n"
        "- Keep the explanation short (markdown is okay).\n"
        '- Return JSON ONLY: {"verdict":"supported|partially_supported|unsupported","confidence":0.0-1.0,"reasoningMd":"..."}\n'
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
