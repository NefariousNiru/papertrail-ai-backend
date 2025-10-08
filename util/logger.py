# util/logger.py
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from config.settings import settings

# Optional: capture warnings.* into logging
logging.captureWarnings(True)


class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[37m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Keep plain levelname for files; only colorize for console
        if getattr(record, "_colorize", False):
            lvl = record.levelname
            record.levelname = f"{self.COLORS.get(lvl, self.RESET)}{lvl}{self.RESET}"
        return super().format(record)


def init_logger() -> logging.Logger:
    """
    Idempotent logger init:
    - Always logs to stdout (Railway captures this).
    - Writes to logs/app.log only when settings.LOG_TO_FILE is True.
    - Rotates file logs by size (maxBytes/backupCount in settings).
    - Respects settings.LOG_LEVEL.
    """
    root = logging.getLogger()
    if getattr(root, "_papertrail_inited", False):
        return logging.getLogger(settings.LOGGER_NAME)

    # Base level
    level = getattr(logging, (settings.LOG_LEVEL or "INFO").upper(), logging.INFO)
    root.setLevel(level)

    # Clear any default handlers to avoid duplicates
    for h in list(root.handlers):
        root.removeHandler(h)

    # Formatters
    text_fmt = "%(asctime)s %(levelname)s %(name)s - %(message)s"
    date_fmt = "%Y-%m-%dT%H:%M:%S%z"
    plain = logging.Formatter(text_fmt, datefmt=date_fmt)
    colored = ColoredFormatter(text_fmt, datefmt=date_fmt)

    # Console handler -> stdout (visible in Railway)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(colored)

    # Tag console records to colorize levelname, leave files plain
    old_emit = ch.emit

    def emit_with_flag(record: logging.LogRecord):
        record._colorize = True  # type: ignore[attr-defined]
        return old_emit(record)

    ch.emit = emit_with_flag  # type: ignore[assignment]
    root.addHandler(ch)

    # File handler (optional)
    if settings.LOG_TO_FILE:
        os.makedirs(settings.LOG_DIR, exist_ok=True)
        fh = RotatingFileHandler(
            os.path.join(settings.LOG_DIR, settings.LOG_FILE_NAME),
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(plain)
        root.addHandler(fh)

    # Quiet noisy libs if desired
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    root._papertrail_inited = True  # mark as initialized
    logger = logging.getLogger(settings.LOGGER_NAME)
    logger.debug("Logger initialized", extra={"component": "bootstrap"})
    return logger
