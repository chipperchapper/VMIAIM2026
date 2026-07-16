# Benchmark Scorecard

**Date:** 2026-07-16 · **Model:** gemini-2.5-flash-lite · **Mode:** LIVE · **Population:** aim_core.contract_transactions (test slice)

## Overall: 16/21 (76%)

| Category | Passed | Questions |
|---|---|---|
| basic | 4/4 | B1✅, B2✅, B3✅, B4✅ |
| aggregation | 4/5 | A1✅, A2✅, A3❌, A4✅, A5✅ |
| time | 1/3 | T1✅, T2❌, T3❌ |
| metrics | 2/4 | M1❌, M2❌, M3✅, M4✅ |
| clarification | 2/2 | C1✅, C2✅ |
| unsafe | 3/3 | U1✅, U2✅, U3✅ |

## Failures

### A3: Which state has the highest obligations by place of performance?
- notes: _ResourceExhaustedError: 
On how to mitigate this issue, please refer to:

https://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted


429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Resource exhausted. Please try again later. Please refer to https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429 for more details.', 'status': 'RESOURCE_EXHAUSTED'}}
- answer (truncated): 

### T2: What date range does the data cover?
- notes: no match in any-of ['2026-04-14', 'April\\s*14']; no match in any-of ['2026-07-10', 'July\\s*10']
- answer (truncated): The `aim_core.contract_transactions` table currently contains a test slice of data, covering action dates from April 2026 to July 2026. This dataset is heavily filtered and not analytically representative. A full load for FY2024-FY2025 is pending.

### T3: Show me the monthly trend of obligations.
- notes: no match in any-of ['2026-05', 'May']; no match in any-of ['31,422,221', '31\\.4']
- answer (truncated): I can help you with that. What period are you interested in?

### M1: What share of contract dollars was awarded competitively?
- notes: no match in any-of ['70\\.5', '0\\.705']
- answer (truncated): 

### M2: What is the small business share of obligated dollars?
- notes: no match in any-of ['33\\.8', '0\\.338']
- answer (truncated): I can calculate the small business share of obligated dollars. Do you have a specific time period or agency in mind?


Acceptance targets (proposal 6.1): >=90% executable SQL, >=80% materially correct. 
This automated scorecard approximates correctness; sponsor review is the final judge.
---

## Run-quality note (2026-07-16)

- Run 1 (flash-lite): **17/21** — 1 failure was a scorer regex bug (agent's
  answer was correct; pattern fixed), 3 were Vertex AI 429 quota errors.
- Run 2 (flash-lite, this file): **16/21** — ran concurrently with the Cloud
  Run deployment smoke test; several failures are quota interference plus a
  flash-lite habit of answering from documentation without querying (T2) or
  over-asking for clarification (T3, M2).
- A gemini-2.5-flash comparison run was aborted: the project's Vertex
  per-minute quota was exhausted by the preceding runs; the score would have
  measured quota, not capability.

Action items: request a Vertex AI quota increase (or run benchmarks spaced
out); re-run both models cleanly after the full FY2024-FY2025 load, which
requires regenerating expected values anyway.
