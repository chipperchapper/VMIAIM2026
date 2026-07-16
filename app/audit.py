"""Audit logging (proposal §5.3: log question, SQL, status, duration, error class)."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import REPO_ROOT, logger

AUDIT_PATH = REPO_ROOT / "logs" / "audit.jsonl"


class AuditLogger:
    def __init__(self, path: Path = AUDIT_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **fields) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except OSError as e:  # never let auditing break the agent
            logger.warning("audit write failed: %s", e)


class RateLimiter:
    """Simple sliding-window limiter: max queries per minute."""

    def __init__(self, max_per_minute: int = 12):
        self.max_per_minute = max_per_minute
        self._times: list[float] = []

    def check(self) -> tuple[bool, str]:
        now = time.time()
        self._times = [t for t in self._times if now - t < 60]
        if len(self._times) >= self.max_per_minute:
            return False, f"Rate limit: max {self.max_per_minute} queries/minute. Wait a moment."
        return True, ""

    def record(self) -> None:
        self._times.append(time.time())
