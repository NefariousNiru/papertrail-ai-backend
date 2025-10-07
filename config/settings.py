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
    APP_ENV: str = Field(..., validation_alias="APP_ENV")
    ALLOWED_ORIGIN: str = Field(..., validation_alias="ALLOWED_ORIGIN")
    ANTHROPIC_API_URL: str = Field(..., validation_alias="ANTHROPIC_API_URL")
    ANTHROPIC_MODEL: str = Field(..., validation_alias="ANTHROPIC_MODEL")
    REDIS_URL: str = Field(..., validation_alias="REDIS_URL")
    PERSISTENCE_TTL_SECONDS: str = Field(
        ..., validation_alias="PERSISTENCE_TTL_SECONDS"
    )
    RATE_LIMIT_TIMES: str = Field(..., validation_alias="RATE_LIMIT_TIMES")
    RATE_LIMIT_SECONDS: int = Field(..., validation_alias="RATE_LIMIT_SECONDS")
    MAX_FILE_MB: int = Field(..., validation_alias="MAX_FILE_MB")
    TRUST_PROXY: bool = Field(..., validation_alias="TRUST_PROXY")


try:
    settings = Settings()
except ValidationError as e:
    print("❌ Missing/invalid environment variables:", file=sys.stderr)
    # Print each error in a compact way
    for err in e.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "")
        print(f" - {loc}: {msg}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"❌ Settings initialization failed: {e}", file=sys.stderr)
    sys.exit(1)
