# Hosted Analytics Agent — DoD Contracts Assistant

A conversational analytics agent that answers plain-English questions about
US Department of Defense contract awards (USAspending.gov, FY2024–FY2025,
8.9M transactions / ~$938B) by writing and executing **read-only** BigQuery
SQL — with the query, method, and metric definitions shown for every answer.

Built for the VMI AIM 2026 two-week intern project. See
[docs/how-it-works.html](docs/how-it-works.html) for a plain-English visual
explainer and [docs/decision-log.md](docs/decision-log.md) for why things are
the way they are.

## Architecture (one paragraph)

A single FastAPI service ([app/main.py](app/main.py)) serves a chat page and
runs a **Google ADK** agent (Gemini via **Vertex AI** — authenticated by
identity, no model API key anywhere). The agent has three tools
([app/tools/bq_tools.py](app/tools/bq_tools.py)); every query passes a
SELECT-only validator + dataset allowlist, a free BigQuery dry-run cost check,
then executes with a 1 GB bytes-billed cap, 30 s timeout, and 100-row limit,
and is written to an audit log. The agent's knowledge (tables, glossary,
approved metrics) lives in [semantics/](semantics/) YAML and is compiled into
its system instruction at startup. Data layers: `aim_raw` (as downloaded) →
`aim_core` (cleaned, typed, deduped) in BigQuery project `vmi-aim-2026`.

## Prerequisites

- Python 3.12+
- Google Cloud CLI (`gcloud`, includes `bq`)
- A Google account with access to GCP project `vmi-aim-2026`

## Setup

```bash
git clone https://github.com/chipperchapper/VMIAIM2026.git
cd VMIAIM2026
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt

gcloud auth login                       # your user identity (CLI)
gcloud auth application-default login   # identity for Python libraries
gcloud config set project vmi-aim-2026

cp .env.example .env                    # defaults are correct for this project
```

`.env` notes: `SAFETY_SWITCH=DRY_RUN` (default) validates SQL but never
executes; for real answers set `SAFETY_SWITCH=LIVE` **and**
`REQUIRE_EXPLICIT_LIVE=true`. No secrets belong in `.env` — model auth is
your Google identity via Vertex AI.

## Run locally

```bash
python -m uvicorn app.main:app --port 8080
# open http://localhost:8080
```

> Note: `adk web` / `adk run app` are confused by the reference `agent.py` at
> the repo root; use uvicorn (above) or the ADK dev UI is not required.

## Tests

```bash
python -m pytest tests/ -v          # SQL guardrail tests (no cloud needed)
python evals/validate_metrics.py    # metric definitions vs BigQuery (needs ADC)
SAFETY_SWITCH=LIVE REQUIRE_EXPLICIT_LIVE=true python evals/run_benchmark.py
                                    # full 21-question benchmark (uses model quota)
```

Latest results: 9/9 data-quality checks, 3/3 metrics validated,
benchmark 19/21 (90%) with 5/5 unsafe requests blocked —
see [evals/results.md](evals/results.md) and
[evals/metric_validation.md](evals/metric_validation.md).

## Data pipeline (rerunnable)

```bash
python data/ingest.py                # discover -> download (~2.2 GB) -> trim -> manifest
# load staged files to BigQuery (see data/ingest.py output), then:
# run data/transform.sql  -> rebuilds aim_core.contract_transactions
# run data/quality_checks.sql -> every row must say PASS
python evals/compute_ground_truth.py # regenerate independent expected values
```

Provenance (source URLs, dates, sizes, row counts) is recorded in
`data/manifest.json`. Column slice rationale: [docs/column-slice.md](docs/column-slice.md).

## Deploy (Cloud Run)

```bash
gcloud run deploy hosted-analytics-agent \
  --source . --project=vmi-aim-2026 --region=us-east1 \
  --service-account=hosted-analytics-agent@vmi-aim-2026.iam.gserviceaccount.com \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=True,GOOGLE_CLOUD_PROJECT=vmi-aim-2026,GOOGLE_CLOUD_LOCATION=global,AGENT_MODEL=gemini-2.5-flash-lite,SAFETY_SWITCH=LIVE,REQUIRE_EXPLICIT_LIVE=true,BQ_LOCATION=US,BUILD_ID=$(git rev-parse --short HEAD)" \
  --set-secrets="APP_PASSWORD=APP_PASSWORD:latest" \
  --allow-unauthenticated \
  --min-instances=0 --max-instances=2 --memory=512Mi --cpu=1 --concurrency=10 --timeout=120
```

Current service: `https://hosted-analytics-agent-171286699495.us-east1.run.app`
(**public** URL, but every `/api/*` call requires the shared password —
decision D6). The password lives only in Secret Manager (`APP_PASSWORD`,
value set via the console UI, never in code or chat); the UI shows a lock
screen and sends it as an `X-App-Password` header. To rotate it, add a new
secret version in the console — new instances pick up `:latest` on the
next deploy or scale-up.

The runtime service account can ONLY run read-only BigQuery jobs and call
Vertex AI (`bigquery.jobUser`, `bigquery.dataViewer`, `aiplatform.user`),
plus WRITER on the `aim_analytics` dataset only (feedback rows, D7).
No service-account keys exist. The `OPENAI_API_KEY` secret in Secret Manager
is empty/unused (Vertex AI made it unnecessary).

## Self-learning loop (D7)

Every answer in the web UI has 👍/👎 buttons. Feedback flows:

```
UI thumbs → POST /api/feedback → aim_analytics.agent_feedback (BigQuery)
                                        │
        agent instruction  ←  learned examples (thumbs-up Q→SQL pairs that
        (rebuilt per call)     still pass the SQL validator; max 12; 30-min
                               cache, refreshed instantly on new thumbs-up)
```

- Setup (one-time): `python data/create_feedback_table.py`
- Inspect what it has learned:
  `SELECT * FROM aim_analytics.agent_feedback ORDER BY ts DESC`
- Un-learn something: delete its row(s) — examples vanish at the next refresh.
- Free-text comments are for human review only; they never enter the prompt.

## Logs & troubleshooting

- Local: every query in `logs/audit.jsonl`; server output in the terminal
- Cloud: `gcloud run services logs read hosted-analytics-agent --region=us-east1 --limit=100`
- **429 RESOURCE_EXHAUSTED**: the project's Vertex AI per-minute quota is
  small; pace batch runs (the benchmark runner already retries + paces) or
  request a quota increase (Console → Quotas → Vertex AI)
- Agent invents nothing by design: if it says a metric/data isn't available,
  check [semantics/](semantics/) — adding knowledge there requires no code

## Costs

- BigQuery: ~10 GB stored (raw + core) → ~$0.20/month; queries are capped at
  1 GB scanned each (free tier: 1 TB/month)
- Cloud Run: scales to zero; effectively $0 at demo traffic
- Vertex AI (Gemini Flash-Lite): ~$0.001 per question
- Budget guard: sponsor's $25 alert on the project

## Teardown

```bash
gcloud run services delete hosted-analytics-agent --region=us-east1 --project=vmi-aim-2026
bq rm -r -f vmi-aim-2026:aim_raw
bq rm -r -f vmi-aim-2026:aim_core
bq rm -r -f vmi-aim-2026:aim_analytics
gcloud secrets delete OPENAI_API_KEY --project=vmi-aim-2026
gcloud iam service-accounts delete hosted-analytics-agent@vmi-aim-2026.iam.gserviceaccount.com
# Artifact Registry images: Console -> Artifact Registry -> cloud-run-source-deploy -> delete
```

Deletion is irreversible — the raw zips + staged files under `data/` (local)
and this repository are the recovery path.
