# Retrospective — Hosted Analytics Agent

**Project:** VMI AIM 2026 two-week intern project · **Written:** 2026-07-17

## What worked

- **Verify-then-trust at every layer.** The pipeline's guards each caught a
  real problem: the schema guard caught USAspending renaming the congressional
  district column (dictionary said one name, real files another); the per-row
  DoD check held across 8.9M rows; quality checks reconciled $937.7B to the
  penny; metric validation caught nothing — because computing expectations
  independently (Python over local files vs SQL in BigQuery) had already
  forced the definitions to be precise.
- **Test slice before full load.** Proving the entire path (download → trim →
  load → clean → query → agent → benchmark) on 204 rows made the 8.9M-row run
  almost boring — every failure mode had already been met at small scale.
- **Identity-based auth (Vertex AI + ADC).** Zero API keys anywhere: nothing
  to store, rotate, or leak. The planned `OPENAI_API_KEY` secret was never
  needed.
- **Semantic layer as YAML.** "Make the agent smarter" became an editing
  task, not a coding task: glossary entries (Army → Department of the Army),
  metric definitions, and caveats all live in version-controlled YAML that
  compiles into the system prompt.
- **The benchmark as a design tool.** Writing questions with independently
  computed answers exposed real behaviors (month-vs-year-month ambiguity,
  answering from documentation instead of querying) that demos never would.

## What didn't work (and what it taught)

- **Vertex AI quota on a fresh project is tiny.** Batch benchmark runs hit
  429s; one model-comparison run had to be abandoned. Lesson: request quota
  early, and design batch tooling with retry + pacing from the start.
- **gemini-2.5-flash-lite is variably lazy.** It once wrote SQL with a
  Russian LIMIT (лимит), occasionally answers from its briefing without
  querying, and once denied an approved metric existed. Each incident became
  an instruction improvement or a documented failure mode; the model-tier
  benchmark comparison is the right way to decide if the 4x cost saving is
  worth it.
- **Long-running local jobs vs. app restarts.** Multi-minute background jobs
  (8.9M-row Python passes) were killed twice by environment restarts. Fix
  that emerged: compute expensive results once, persist them
  (ground_truth.json), and let downstream consumers reuse the artifact.
- **Google Drive is not a dev directory.** Sync conflicts with git/venvs were
  avoided by moving to C:\dev early — should have started there.
- **Real data is messier than documentation.** Lockheed Martin appears under
  two parent-name spellings; some state codes are empty; DoD program fields
  are mostly NULL. None of these are bugs — they're caveats the agent now
  states in answers.

## What I learned

- Trustworthy conversational analytics is mostly NOT the model: it's the
  data dictionary, the approved metric definitions, the read-only guardrails,
  and the evaluation harness. The model is swappable (one env var).
- "Materially correct" needs an independent ground truth. An answer that
  *sounds* right and an answer that matches a separately computed number are
  different things.
- Cost control is architectural: dry-run first, bytes-billed caps, row
  limits, scale-to-zero — the $25 budget was never at risk.

## What should be built next

1. **Vendor-name normalization** (dedupe parent spellings via
   recipient_parent_uei) — the single highest-value data improvement.
2. **Model tier decision** via the Flash vs Flash-Lite benchmark once quota
   allows; consider Flash as the default if variance matters.
3. **Public access + sponsor demo** (one-flag redeploy), then feedback loop.
4. **aim_analytics views** for the approved metrics so BI tools can reuse the
   exact same definitions the agent uses.
5. Stretch (per proposal): Slack interface reusing the same /api/chat
   endpoint; charts from structured results; session memory.
