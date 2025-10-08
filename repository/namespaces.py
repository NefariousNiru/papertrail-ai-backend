# repository/namespaces.py
from typing import Final

ROOT: Final[str] = "papertrail"

JOBS: Final[str] = f"{ROOT}:jobs"
CLAIMS: Final[str] = f"{ROOT}:claims"  # e.g., per-job claim snapshots
STREAMS: Final[str] = f"{ROOT}:streams"  # e.g., resumable cursors
TEMPFILES: Final[str] = f"{ROOT}:tmpfiles"
VERIFICATIONS: Final[str] = f"{ROOT}:verifications"
BLOBS: Final[str] = f"{JOBS}:blob"
