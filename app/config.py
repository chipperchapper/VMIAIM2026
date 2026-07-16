"""Configuration and safety switch.

Mirrors the bq-slack-app pattern: a DRY_RUN/LIVE safety switch with an
explicit opt-in required for LIVE, plus hard cost/row limits that the
SQL tool enforces regardless of what the model asks for.
"""
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("hosted_analytics_agent")

REPO_ROOT = Path(__file__).resolve().parents[1]
SEMANTICS_DIR = REPO_ROOT / "semantics"


@dataclass
class Config:
    safety_switch: str          # DRY_RUN (validate only) or LIVE (execute)
    project_id: str
    bq_location: str
    allowed_datasets: tuple[str, ...]
    max_rows: int               # rows returned to the model
    max_bytes_billed: int       # hard BigQuery cost cap per query
    query_timeout_s: int
    model: str                  # ADK model id (Gemini via Vertex AI by default)

    @classmethod
    def load(cls) -> "Config":
        safety_switch = os.getenv("SAFETY_SWITCH", "DRY_RUN").upper()
        if safety_switch == "LIVE" and os.getenv("REQUIRE_EXPLICIT_LIVE") != "true":
            raise RuntimeError("LIVE mode requires REQUIRE_EXPLICIT_LIVE=true")
        return cls(
            safety_switch=safety_switch,
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "vmi-aim-2026"),
            bq_location=os.getenv("BQ_LOCATION", "US"),
            allowed_datasets=tuple(
                d.strip()
                for d in os.getenv("ALLOWED_DATASETS", "aim_raw,aim_core,aim_analytics").split(",")
                if d.strip()
            ),
            max_rows=int(os.getenv("MAX_ROWS", "100")),
            max_bytes_billed=int(os.getenv("MAX_BYTES_BILLED", "1000000000")),  # 1 GB
            query_timeout_s=int(os.getenv("QUERY_TIMEOUT_S", "30")),
            model=os.getenv("AGENT_MODEL", "gemini-flash-latest"),
        )

    @property
    def is_dry_run(self) -> bool:
        return self.safety_switch == "DRY_RUN"


CONFIG = Config.load()
logger.info(
    "%s mode | project=%s | datasets=%s | max_bytes=%s",
    CONFIG.safety_switch, CONFIG.project_id, CONFIG.allowed_datasets, CONFIG.max_bytes_billed,
)
