# Metric Validation Report

**Date:** 2026-07-17 · **Population:** aim_core.contract_transactions (8,910,250 transactions, 2023-10-01..2025-09-30 (from ground_truth.json))

Two fully independent computation paths: pure Python over the local staged
CSV vs. the metric formula SQL executed in BigQuery. Agreement validates the
definition AND the load pipeline end-to-end.

| Metric | Expected (Python/local) | Actual (SQL/BigQuery) | Verdict |
|---|---|---|---|
| competition_rate | 0.552377 | 0.552377 | ✅ MATCH |
| small_business_share | 0.210495 | 0.210495 | ✅ MATCH |
| contractor_concentration_hhi | 200.535476 | 200.535476 | ✅ MATCH |

Interpretation:
- competition_rate = 55.2% of dollars competitively awarded
- small_business_share = 21.0% of dollars to small businesses
- HHI = 201 (>2500 = highly concentrated by antitrust convention)