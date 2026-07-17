# Model Comparison — gemini-2.5-flash vs gemini-2.5-flash-lite

**Date:** 2026-07-17 · **Benchmark:** 21 questions vs full FY2024–FY2025 data
(independently computed expected answers — see ground_truth.json)

| | flash-lite | flash |
|---|---|---|
| Scored | **19/21 (90%)** | **19/21 (90%)** |
| After scorer-artifact review | 19/21 | effectively **20/21** (T3 answer was numerically perfect; scorer regex missed its table format) |
| Unsafe requests blocked | 5/5 | 5/5 |
| Typical answer latency | ~8–14 s | ~7–19 s |
| Cost per question (approx) | ~$0.001 | ~$0.004 |

## Failure character (the real difference)

- **flash-lite** failures are *variance*: it once denied an approved metric
  existed (M2), historically wrote a Cyrillic SQL keyword, and sometimes
  answers from documentation without querying. Unpredictable but cheap.
- **flash** failures are *boundary conditions*: it wrote a wide scan that hit
  the 1 GB bytes-billed cap (B4) and honestly reported it. More consistent
  reasoning, slightly costlier queries.

## Recommendation

Keep **flash-lite as the default** for the demo (variance is acceptable at
interactive use, cost is 4x lower), but document that production use with
higher correctness demands should use **flash** — switching is one env var
(`AGENT_MODEL`). Revisit after a Vertex quota increase allows repeated runs
for tighter confidence intervals (single-run scores carry ±1–2 question noise).

Raw outputs: results.json / results.md and the results_flash.* copies all
currently hold the **flash** run (the flash run overwrote the shared results
file before the copy). The flash-lite run of record (19/21, 2026-07-17,
failures: T1 month-ambiguity — since fixed via instruction — and M2 metric
denial) is documented in the scorecard history; re-run
`AGENT_MODEL=gemini-2.5-flash-lite python evals/run_benchmark.py` to
regenerate it. TODO: make run_benchmark.py write model-named result files to
prevent this overwrite class.
