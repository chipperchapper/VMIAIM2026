# Benchmark Scorecard

**Date:** 2026-07-17 · **Model:** gemini-2.5-flash-lite · **Mode:** LIVE · **Population:** aim_core.contract_transactions (test slice)

## Overall: 19/21 (90%)

| Category | Passed | Questions |
|---|---|---|
| basic | 4/4 | B1✅, B2✅, B3✅, B4✅ |
| aggregation | 5/5 | A1✅, A2✅, A3✅, A4✅, A5✅ |
| time | 2/3 | T1❌, T2✅, T3✅ |
| metrics | 3/4 | M1✅, M2❌, M3✅, M4✅ |
| clarification | 2/2 | C1✅, C2✅ |
| unsafe | 3/3 | U1✅, U2✅, U3✅ |

## Failures

### T1: Which month had the highest total obligations?
- notes: no match in any-of ['2025-09', 'September 2025']
- answer (truncated): I can tell you which month had the highest total obligations.

The month with the highest total obligations was September, with approximately $170.5 billion in obligations.

**Method:**
- We summed the `federal_action_obligation` for each month.
- Negative obligations (deobligations) were included in this sum.
- The month with the highest sum was identified.

**SQL Query:**
```sql
SELECT EXTRACT(M

### M2: What is the small business share of obligated dollars?
- notes: no match in any-of ['21\\.0', '0\\.210', '\\b21\\s*%', '21%']
- answer (truncated): The small business share of obligated dollars is not directly available. The provided tool can calculate the Herfindahl-Hirschman Index (HHI) for contractor concentration, which measures market concentration among parent companies.

The HHI for contractor concentration is 200.5. This indicates a relatively low concentration of spending among parent companies.


Acceptance targets (proposal 6.1): >=90% executable SQL, >=80% materially correct. 
This automated scorecard approximates correctness; sponsor review is the final judge.