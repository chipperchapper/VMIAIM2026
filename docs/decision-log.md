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

*(Next expected entries: D5 — full FY2024-FY2025 load & re-validation; D6 — public access decision before sponsor demo.)*
