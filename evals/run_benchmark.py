"""Run the 20+ question benchmark against the live agent (proposal section 6).

Each question runs in a FRESH session (no cross-question contamination).
Scoring is automatic via the regex expectations in benchmark_questions.yaml.
Writes evals/results.md (scorecard) and evals/results.json (full detail).

Usage:  SAFETY_SWITCH=LIVE REQUIRE_EXPLICIT_LIVE=true python evals/run_benchmark.py
"""
import asyncio
import json
import re
import sys
import time
import uuid
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from google.adk.runners import Runner            # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types                   # noqa: E402

from app.agent import root_agent                 # noqa: E402
from app.config import CONFIG                    # noqa: E402

QUESTIONS = yaml.safe_load(open(REPO / "evals" / "benchmark_questions.yaml", encoding="utf-8"))["questions"]


async def ask(runner: Runner, service: InMemorySessionService, question: str) -> tuple[str, int]:
    session_id = str(uuid.uuid4())
    await service.create_session(app_name="bench", user_id="bench", session_id=session_id)
    message = types.Content(role="user", parts=[types.Part(text=question)])
    answer, tool_calls = "", 0
    async for event in runner.run_async(user_id="bench", session_id=session_id, new_message=message):
        if not event.content or not event.content.parts:
            continue
        for part in event.content.parts:
            if getattr(part, "function_call", None):
                tool_calls += 1
        if event.is_final_response():
            answer = "".join(p.text or "" for p in event.content.parts if getattr(p, "text", None))
    return answer, tool_calls


def score(q: dict, answer: str) -> tuple[bool, list[str]]:
    notes = []
    ok = True
    for pattern in q.get("expect", []):
        if not re.search(pattern, answer, re.IGNORECASE):
            ok = False
            notes.append(f"missing required /{pattern}/")
    for group in q.get("expect_any", []):
        if not any(re.search(p, answer, re.IGNORECASE) for p in group):
            ok = False
            notes.append(f"no match in any-of {group}")
    return ok, notes


async def main() -> None:
    service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="bench", session_service=service)

    results = []
    for q in QUESTIONS:
        started = time.time()
        answer, tool_calls, error = "", 0, None
        for attempt in range(3):  # retry model-quota 429s with backoff
            try:
                answer, tool_calls = await ask(runner, service, q["question"])
                error = None
                break
            except Exception as e:
                error = f"{type(e).__name__}: {e}"
                if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                    await asyncio.sleep(25 * (attempt + 1))
                else:
                    break
        await asyncio.sleep(3)  # pace requests to stay under Vertex quota
        duration = time.time() - started
        passed, notes = score(q, answer) if not error else (False, [error])
        results.append({
            "id": q["id"], "category": q["category"], "question": q["question"],
            "passed": passed, "notes": notes, "answer": answer,
            "tool_calls": tool_calls, "seconds": round(duration, 1),
        })
        print(f"{'PASS' if passed else 'FAIL'} {q['id']} ({duration:.0f}s) {q['question'][:60]}")

    # ---- scorecard ----
    total = len(results)
    passed_n = sum(r["passed"] for r in results)
    by_cat: dict[str, list] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)

    lines = [
        "# Benchmark Scorecard",
        "",
        f"**Date:** {date.today().isoformat()} · **Model:** {CONFIG.model} · "
        f"**Mode:** {CONFIG.safety_switch} · **Population:** aim_core.contract_transactions (test slice)",
        "",
        f"## Overall: {passed_n}/{total} ({passed_n / total:.0%})",
        "",
        "| Category | Passed | Questions |",
        "|---|---|---|",
    ]
    for cat, rs in by_cat.items():
        lines.append(f"| {cat} | {sum(r['passed'] for r in rs)}/{len(rs)} | "
                     + ", ".join(f"{r['id']}{'✅' if r['passed'] else '❌'}" for r in rs) + " |")
    lines += ["", "## Failures", ""]
    fails = [r for r in results if not r["passed"]]
    if not fails:
        lines.append("None.")
    for r in fails:
        lines.append(f"### {r['id']}: {r['question']}")
        lines.append(f"- notes: {'; '.join(r['notes'])}")
        lines.append(f"- answer (truncated): {r['answer'][:400]}")
        lines.append("")
    lines += [
        "",
        f"Acceptance targets (proposal 6.1): >=90% executable SQL, >=80% materially correct. ",
        f"This automated scorecard approximates correctness; sponsor review is the final judge.",
    ]
    (REPO / "evals" / "results.md").write_text("\n".join(lines), encoding="utf-8")
    (REPO / "evals" / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n{passed_n}/{total} passed -> evals/results.md")


if __name__ == "__main__":
    asyncio.run(main())
