# Metric Validation Report

**Date:** 2026-07-16 · **Population:** aim_core.contract_transactions (204 transactions, test slice Apr-Jul 2026)

Two fully independent computation paths: pure Python over the local staged
CSV vs. the metric formula SQL executed in BigQuery. Agreement validates the
definition AND the load pipeline end-to-end.

| Metric | Expected (Python/local) | Actual (SQL/BigQuery) | Verdict |
|---|---|---|---|
| competition_rate | 0.705085 | 0.705085 | ✅ MATCH |
| small_business_share | 0.338174 | 0.338174 | ✅ MATCH |
| contractor_concentration_hhi | 1058.616298 | 1058.616298 | ✅ MATCH |

Interpretation on this test slice:
- competition_rate = 70.5% of dollars competitively awarded
- small_business_share = 33.8% of dollars to small businesses
- HHI = 1059 (>2500 = highly concentrated by antitrust convention; small samples skew high)

NOTE: values are from the 204-row test slice and are NOT representative;
re-run this script after the full FY2024-FY2025 load to re-validate.