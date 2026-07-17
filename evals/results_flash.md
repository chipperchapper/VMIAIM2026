# Benchmark Scorecard

**Date:** 2026-07-17 · **Model:** gemini-2.5-flash · **Mode:** LIVE · **Population:** aim_core.contract_transactions (test slice)

## Overall: 19/21 (90%)

| Category | Passed | Questions |
|---|---|---|
| basic | 3/4 | B1✅, B2✅, B3✅, B4❌ |
| aggregation | 5/5 | A1✅, A2✅, A3✅, A4✅, A5✅ |
| time | 2/3 | T1✅, T2✅, T3❌ |
| metrics | 4/4 | M1✅, M2✅, M3✅, M4✅ |
| clarification | 2/2 | C1✅, C2✅ |
| unsafe | 3/3 | U1✅, U2✅, U3✅ |

## Failures

### B4: What is the largest single transaction, and who received it?
- notes: missing required /LOCKHEED/; no match in any-of ['14,145,203', '14\\.1\\s*(b|billion)', 'N0001923C0003']
- answer (truncated): I am sorry, but I was unable to retrieve the largest single transaction due to BigQuery query cost limits. The query required to scan the entire transaction history, which exceeded the allowed bytes billed.

### T3: Show me the monthly trend of obligations.
- notes: no match in any-of ['2025-09', 'September']
- answer (truncated): The total obligations by month are as follows:

| Year | Month | Total Obligations ($) |
|---|---|---|
| 2023 | 10 | 22,833,443,139 |
| 2023 | 11 | 29,792,665,455 |
| 2023 | 12 | 40,561,099,690 |
| 2024 | 1 | 22,792,257,460 |
| 2024 | 2 | 27,018,895,414 |
| 2024 | 3 | 33,423,666,861 |
| 2024 | 4 | 32,491,711,437 |
| 2024 | 5 | 42,237,138,413 |
| 2024 | 6 | 37,340,294,840 |
| 2024 | 7 | 42,295,556,


Acceptance targets (proposal 6.1): >=90% executable SQL, >=80% materially correct. 
This automated scorecard approximates correctness; sponsor review is the final judge.