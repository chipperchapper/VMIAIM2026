# Decision Log

Format per proposal §7.2: decision · alternatives considered · reason · date.

---

## D1 — Dataset: USAspending.gov DoD contract awards, FY2024–FY2025

- **Date:** 2026-07-14
- **Decision:** Use US Department of Defense contract award data from USAspending.gov, limited to two fiscal years (FY2024 and FY2025, ~2.2 GB zipped / ~12–16 GB raw), trimmed to ~30–40 analytically useful columns out of 200+.
- **Alternatives considered:** Amazon Reviews 2023 Video Games category (McAuley Lab, UCSD); BTS Airline On-Time Performance. Earlier candidates screened out: Olist e-commerce (non-commercial license, small scale), SIPRI/COW military datasets (too small to justify a warehouse), UCDP conflict events (heavy demo tone).
- **Reason:** Public domain (no license restrictions), large enough to genuinely justify a cloud warehouse, engaging domain, and questions map directly onto a realistic internal analytics agent ("which contractors, which agencies, how competed"). Two years keeps ingestion feasible in the 10-day window while still supporting year-over-year trend questions.
- **Fallback trigger:** If raw data is not loaded and queryable by end of Day 4, switch to BTS Flights (2–3 years) with no architecture change.
- **Details:** See [dataset-decision-memo.md](dataset-decision-memo.md).

---

## D2 — Warehouse & hosting: BigQuery + Cloud Run (per sponsor's setup guide)

- **Date:** 2026-07-14
- **Decision:** BigQuery (datasets `aim_raw`/`aim_core`/`aim_analytics`) + one Cloud Run service, project `vmi-aim-2026`, region `us-east1`.
- **Alternatives considered:** PostgreSQL on Cloud SQL (proposal's open-source path).
- **Reason:** Sponsor's INITIAL_GOOGLE_CLOUD_SETUP_GUIDE prescribes this stack and explains the fit: analytical columnar warehouse for a 12–16 GB public dataset, dry-run + bytes-billed cost controls, scales-to-zero hosting, single-project ops. Cloud SQL would add instance management and lacks per-query byte caps.

---

## D3 — Agent framework: Google ADK + Gemini on Vertex AI

- **Date:** 2026-07-15
- **Decision:** Build the agent with Google's Agent Development Kit (`google-adk`), model `gemini-2.5-flash` served through Vertex AI (`GOOGLE_CLOUD_LOCATION=global`), authenticated via Application Default Credentials.
- **Alternatives considered:** OpenAI Agents SDK (suggested in proposal background reading); Anthropic Claude SDK (used by the sponsor's reference app `bq-slack-app`).
- **Reason:** Sponsor direction to mirror the `bq-slack-app` architecture with ADK. Bonus: Vertex AI uses ADC/service-account identity, so **no model API key exists at all** — removes the secret-handling burden (the `OPENAI_API_KEY` secret container remains empty/unused unless we switch). Architecture mirrors the reference app: config safety switch (DRY_RUN/LIVE), SELECT-only validator + dataset allowlist, dry-run-first cost check with bytes-billed cap, JSONL audit log, YAML semantic layer feeding the system prompt.
- **Validated:** 2026-07-15 — guardrail tests 10/10; live end-to-end run answered "top 3 parent companies" with numbers matching manual SQL, disclosed method + SQL.

---

## D4 — Deployment: Cloud Run, private (authenticated) for now

- **Date:** 2026-07-16
- **Decision:** Deployed `hosted-analytics-agent` to Cloud Run (us-east1) from source via Cloud Build; runtime identity = the read-only service account + `roles/aiplatform.user` (granted with intern approval). Deployed **--no-allow-unauthenticated**: only authenticated Google identities can open it. URL: https://hosted-analytics-agent-171286699495.us-east1.run.app
- **Alternatives considered:** public URL (--allow-unauthenticated, the setup guide's default command).
- **Reason:** Intern chose to keep it private while the data is still the test slice; making it public later is a one-flag redeploy. Cost guards unchanged (scale-to-zero, 1 GB/query cap, rate limiter, LIVE-mode double opt-in via env vars).
- **Verified:** 2026-07-16 — /api/meta healthy (build 23a2fde), live chat answered "174 distinct contracts" (correct) in 3.0 s from the cloud.

---

## D5 — Full FY2024–FY2025 load, re-validated end-to-end

- **Date:** 2026-07-17
- **Decision:** Loaded both complete fiscal years (8,910,250 transactions, ~$937.7B) into `aim_raw.dod_contracts_fy2024/fy2025`; rebuilt `aim_core.contract_transactions` (6.8 GB); regenerated all ground truths and benchmark expectations.
- **Validation:** 9/9 quality checks (dollars reconciled to the penny); 3/3 metrics matched independent Python computation to 6 decimals; benchmark 19/21 (90%) with 5/5 unsafe requests blocked. Model comparison run: flash-lite 19/21 vs flash effectively 20/21 (see evals/model_comparison.md) — flash-lite kept as default (4× cheaper), flash documented for higher-stakes use.
- **Data findings recorded:** parent-name spelling variants (Lockheed ×2), sparse DoD program fields, September fiscal-year-end spending spikes, empty state codes for some overseas work.

---

## D6 — Public access with a shared password gate

- **Date:** 2026-07-17
- **Decision:** Redeployed Cloud Run with `--allow-unauthenticated` (public URL) plus an application-level password gate: `/api/*` requires an `X-App-Password` header, constant-time-compared against the `APP_PASSWORD` secret (Secret Manager, readable only by the runtime service account, value set by the intern via the console — never present in chat, repo, or code). UI shows a lock screen; password cached per browser tab.
- **Alternatives considered:** keep private/IAM-only (blocks the sponsor's "open from a normal browser" requirement); Cloud IAP / SSO (out of scope per proposal §1.3).
- **Reason:** Meets the proposal's hosted-URL requirement while preventing anonymous use of Vertex/BigQuery quota. Read-only guardrails and cost caps still bound what password-holders can do. Verified live: page public (200), API 401 without/with wrong password, correct password unlocks (confirmed by intern).
- **URL:** https://hosted-analytics-agent-171286699495.us-east1.run.app

---

## D7 — Self-learning loop: user feedback becomes learned examples

- **Date:** 2026-07-22
- **Decision:** The agent now learns from its users. 👍/👎 buttons under every answer post to a password-gated `/api/feedback` endpoint; rows land in `aim_analytics.agent_feedback` (day-partitioned, plus a local `logs/feedback.jsonl` trace). The agent's instruction is now built dynamically per model call: thumbs-up question→SQL pairs are re-checked against the SQL validator and injected as up to 12 few-shot "learned examples" (30-minute cache, invalidated immediately by new thumbs-up feedback). The empty `aim_analytics` dataset finally has a job.
- **Alternatives considered:** model fine-tuning (cost, quota, and irreversibility — wrong fit at this scale); learning automatically from every successful query without a human signal (would learn plausible-but-wrong answers as happily as right ones).
- **Safety properties:** learned SQL is validated twice (at learn time and, as always, at run time — a poisoned example can never execute anything the validator bans); user free-text comments are stored for human review but **never enter the prompt** (prompt-injection surface); any learning failure degrades to "no learned section", never a broken agent. Also hardened the instruction: in DRY_RUN mode the model must never invent numeric results (observed once locally in testing).
- **Access change required:** the runtime service account needs **WRITER on the `aim_analytics` dataset only** (dataset-level ACL, not project IAM) so the cloud app can insert feedback rows. Reading learned examples already works via its existing `dataViewer`.
- **Verified:** 9 new unit tests (poisoned-SQL exclusion, dedupe, cap, TTL, stale-over-missing, comment isolation) — 19/19 suite green; local end-to-end: UI thumbs-up → BigQuery row → learned example present in the next model call's instruction.
- **Extended same day — three learning channels:** (1) 👍 **examples** (as above); (2) 👎 **anti-examples** — up to 5 confirmed-wrong question→SQL pairs shown as approaches not to repeat; (3) **self-corrections** — when a query errors and a follow-up succeeds within 2 minutes, the (error → working SQL) pair is recorded automatically (`rating='fix'`, no human input) and up to 6 are shown so the agent stops repeating its own past errors. Newest rating per question wins (a question fixed after a 👎 appears only as a good example). All three buckets remain validator-gated. 23/23 tests; fail→succeed→learned verified live.

---

*(Future candidates: vendor-name normalization, model-tier change, IAP, periodic learned-example review job.)*
