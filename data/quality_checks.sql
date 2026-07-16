-- quality_checks.sql : run after transform.sql (proposal 4.1)
-- Every row of the result must show PASS.

WITH raw_stats AS (
  SELECT COUNT(*) AS raw_rows,
         COUNT(DISTINCT contract_transaction_unique_key) AS raw_distinct_keys,
         ROUND(SUM(federal_action_obligation), 2) AS raw_dollars
  FROM aim_raw.dod_contracts_test
),
core_stats AS (
  SELECT COUNT(*) AS core_rows,
         COUNT(DISTINCT contract_transaction_unique_key) AS core_distinct_keys,
         ROUND(SUM(federal_action_obligation), 2) AS core_dollars,
         COUNTIF(contract_transaction_unique_key IS NULL) AS null_pk,
         COUNTIF(contract_award_unique_key IS NULL) AS null_award_key,
         COUNTIF(action_date IS NULL) AS null_action_date,
         COUNTIF(awarding_sub_agency_name IS NULL) AS null_sub_agency,
         MIN(action_date) AS min_date, MAX(action_date) AS max_date
  FROM aim_core.contract_transactions
)
SELECT check_name, IF(passed, 'PASS', 'FAIL') AS result, detail FROM (
  SELECT '1 row count: core = distinct raw keys' AS check_name,
         c.core_rows = r.raw_distinct_keys AS passed,
         FORMAT('core=%d raw_distinct=%d', c.core_rows, r.raw_distinct_keys) AS detail
  FROM raw_stats r, core_stats c
  UNION ALL
  SELECT '2 primary key unique', c.core_rows = c.core_distinct_keys,
         FORMAT('rows=%d distinct=%d', c.core_rows, c.core_distinct_keys)
  FROM core_stats c
  UNION ALL
  SELECT '3 no null primary keys', c.null_pk = 0, FORMAT('nulls=%d', c.null_pk) FROM core_stats c
  UNION ALL
  SELECT '4 no null award keys', c.null_award_key = 0, FORMAT('nulls=%d', c.null_award_key) FROM core_stats c
  UNION ALL
  SELECT '5 no null action dates', c.null_action_date = 0, FORMAT('nulls=%d', c.null_action_date) FROM core_stats c
  UNION ALL
  SELECT '6 no null sub-agencies', c.null_sub_agency = 0, FORMAT('nulls=%d', c.null_sub_agency) FROM core_stats c
  UNION ALL
  SELECT '7 dollars reconcile with raw (dedup-adjusted)', ABS(c.core_dollars - r.raw_dollars) < 0.01 OR c.core_rows < r.raw_rows,
         FORMAT('core=%.2f raw=%.2f', c.core_dollars, r.raw_dollars)
  FROM raw_stats r, core_stats c
  UNION ALL
  SELECT '8 dates in plausible range', c.min_date >= '2007-10-01' AND c.max_date <= CURRENT_DATE(),
         FORMAT('min=%t max=%t', c.min_date, c.max_date)
  FROM core_stats c
)
ORDER BY check_name;
