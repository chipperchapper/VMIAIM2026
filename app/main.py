"""Web entry point: FastAPI serving the chat UI + a /api/chat endpoint that
runs the ADK agent in-process.

Local run:
    python -m uvicorn app.main:app --port 8080 --reload

Cloud Run runs the same app via the Dockerfile (later milestone).
"""
import hmac
import inspect
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel

from typing import Literal

from .agent import root_agent
from .config import CONFIG, logger
from . import learning

APP_NAME = "hosted_analytics_agent"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Shared access password (set via Secret Manager -> env on Cloud Run).
# When unset (e.g. local dev), the gate is disabled.
APP_PASSWORD = os.getenv("APP_PASSWORD", "")


async def require_password(x_app_password: str = Header(default="")) -> None:
    if not APP_PASSWORD:
        return  # gate disabled (local dev)
    if not hmac.compare_digest(x_app_password, APP_PASSWORD):
        raise HTTPException(status_code=401, detail="Password required")


def _build_id() -> str:
    import os
    if os.getenv("BUILD_ID"):        # set at deploy time (no .git in the container)
        return os.environ["BUILD_ID"]
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=Path(__file__).resolve().parents[1],
        ).stdout.strip() or "dev"
    except Exception:
        return "dev"


BUILD_ID = _build_id()

app = FastAPI(title="Hosted Analytics Agent")
_session_service = InMemorySessionService()
_runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=_session_service)


async def _maybe_await(value):
    return await value if inspect.isawaitable(value) else value


class ChatRequest(BaseModel):
    message: str
    session_id: str


class FeedbackRequest(BaseModel):
    session_id: str
    question: str
    answer: str = ""
    sql: str | None = None
    rating: Literal["up", "down"]
    comment: str | None = None


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/meta")
async def meta(_: None = Depends(require_password)) -> dict[str, Any]:
    return {
        "mode": CONFIG.safety_switch,
        "model": CONFIG.model,
        "project": CONFIG.project_id,
        "build": BUILD_ID,
        "dataset_note": (
            "US Department of Defense prime contract transactions from "
            "USAspending.gov. Coverage: complete fiscal years FY2024-FY2025 "
            "(Oct 2023 - Sep 2025), 8.9 million transactions, ~$938B in "
            "obligations. Public domain data, loaded 2026-07-17."
        ),
    }


@app.post("/api/feedback")
async def feedback(req: FeedbackRequest, _: None = Depends(require_password)) -> dict[str, Any]:
    """Store a thumbs-up/down on an answer (self-learning loop, D7)."""
    stored = learning.record_feedback(
        session_id=req.session_id,
        question=req.question,
        sql=req.sql,
        answer=req.answer,
        rating=req.rating,
        comment=req.comment,
        model=CONFIG.model,
        build_id=BUILD_ID,
    )
    return {"ok": True, "stored": stored}


@app.post("/api/chat")
async def chat(req: ChatRequest, _: None = Depends(require_password)) -> dict[str, Any]:
    user_id = "web"
    started = time.time()

    session = await _maybe_await(_session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=req.session_id))
    if session is None:
        await _maybe_await(_session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=req.session_id))

    message = types.Content(role="user", parts=[types.Part(text=req.message)])

    answer = ""
    tool_events: list[dict[str, Any]] = []
    try:
        async for event in _runner.run_async(
            user_id=user_id, session_id=req.session_id, new_message=message
        ):
            if not event.content or not event.content.parts:
                continue
            for part in event.content.parts:
                fc = getattr(part, "function_call", None)
                if fc:
                    tool_events.append({
                        "type": "call",
                        "tool": fc.name,
                        "args": {k: str(v)[:4000] for k, v in (fc.args or {}).items()},
                    })
                fr = getattr(part, "function_response", None)
                if fr:
                    resp = fr.response or {}
                    tool_events.append({
                        "type": "result",
                        "tool": fr.name,
                        "status": str(resp.get("status", "")),
                        "row_count": resp.get("row_count"),
                        "bytes_display": resp.get("bytes_display"),
                        "error": str(resp.get("error", ""))[:500] or None,
                    })
            if event.is_final_response():
                answer = "".join(p.text or "" for p in event.content.parts if getattr(p, "text", None))
    except Exception as e:  # surface a friendly error, log the real one
        logger.exception("chat turn failed")
        return {
            "ok": False,
            "error": f"Something went wrong on our side ({type(e).__name__}). Try again, or rephrase the question.",
        }

    return {
        "ok": True,
        "answer": answer or "(The agent returned no text - try rephrasing.)",
        "tool_events": tool_events,
        "duration_ms": int((time.time() - started) * 1000),
        "mode": CONFIG.safety_switch,
    }
