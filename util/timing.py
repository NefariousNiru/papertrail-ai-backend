# util/timing.py
import time
from contextlib import contextmanager
from typing import Iterator, Optional, Dict, Any
import logging


@contextmanager
def timed(logger: logging.Logger, name: str, **kv: Dict[str, Any]) -> Iterator[None]:
    """
    Usage:
      with timed(logger, "pdf.parse", pages=10):
          ...
    Emits one INFO on exit: "<name>.done ms=<int> key=val ..."
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        dt_ms = int((time.perf_counter() - t0) * 1000)
        suffix = "".join(f" {k}={v}" for k, v in kv.items())
        logger.info("%s.done ms=%d%s", name, dt_ms, suffix)
