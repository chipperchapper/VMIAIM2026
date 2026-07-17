-- transform.sql : aim_raw -> aim_core.contract_transactions
--
-- Cleaning applied (documented per proposal 4.1):
--   1. TRIM all strings; empty strings -> NULL
--   2. period_of_performance_potential_end_date: TIMESTAMP -> DATE
--      (autodetect guessed TIMESTAMP on the raw load)
--   3. naics_code: INT64 -> STRING (codes are identifiers, not quantities)
--   4. Deduplicate on contract_transaction_unique_key (keep latest action_date)
--
-- SOURCE: full FY2024 + FY2025 tables (switched from the test slice on
-- 2026-07-16 after the full load; test slice remains in
-- aim_raw.dod_contracts_test for reference).

CREATE OR REPLACE TABLE aim_core.contract_transactions AS
WITH source AS (
  SELECT * FROM aim_raw.dod_contracts_fy2024
  UNION ALL
  SELECT * FROM aim_raw.dod_contracts_fy2025
),
cleaned AS (
  SELECT
    NULLIF(TRIM(contract_transaction_unique_key), '') AS contract_transaction_unique_key,
    NULLIF(TRIM(contract_award_unique_key), '')       AS contract_award_unique_key,
    NULLIF(TRIM(award_id_piid), '')                   AS award_id_piid,
    NULLIF(TRIM(parent_award_id_piid), '')            AS parent_award_id_piid,
    NULLIF(TRIM(modification_number), '')             AS modification_number,
    NULLIF(TRIM(award_or_idv_flag), '')               AS award_or_idv_flag,

    federal_action_obligation,
    total_dollars_obligated,
    current_total_value_of_award,
    potential_total_value_of_award,

    action_date,
    action_date_fiscal_year,
    period_of_performance_start_date,
    period_of_performance_current_end_date,
    DATE(period_of_performance_potential_end_date)    AS period_of_performance_potential_end_date,

    NULLIF(TRIM(awarding_sub_agency_name), '')        AS awarding_sub_agency_name,
    NULLIF(TRIM(awarding_office_name), '')            AS awarding_office_name,
    NULLIF(TRIM(funding_sub_agency_name), '')         AS funding_sub_agency_name,

    NULLIF(TRIM(recipient_uei), '')                   AS recipient_uei,
    NULLIF(TRIM(recipient_name), '')                  AS recipient_name,
    NULLIF(TRIM(recipient_parent_uei), '')            AS recipient_parent_uei,
    NULLIF(TRIM(recipient_parent_name), '')           AS recipient_parent_name,
    NULLIF(TRIM(recipient_city_name), '')             AS recipient_city_name,
    UPPER(NULLIF(TRIM(recipient_state_code), ''))     AS recipient_state_code,
    NULLIF(TRIM(recipient_country_name), '')          AS recipient_country_name,

    NULLIF(TRIM(primary_place_of_performance_city_name), '')    AS primary_place_of_performance_city_name,
    UPPER(NULLIF(TRIM(primary_place_of_performance_state_code), '')) AS primary_place_of_performance_state_code,
    NULLIF(TRIM(primary_place_of_performance_country_name), '') AS primary_place_of_performance_country_name,
    NULLIF(TRIM(prime_award_transaction_place_of_performance_cd_current), '') AS place_of_performance_congressional_district,

    NULLIF(TRIM(award_type), '')                      AS award_type,
    NULLIF(TRIM(transaction_description), '')         AS transaction_description,
    CAST(naics_code AS STRING)                        AS naics_code,
    NULLIF(TRIM(naics_description), '')               AS naics_description,
    NULLIF(TRIM(product_or_service_code), '')         AS product_or_service_code,
    NULLIF(TRIM(product_or_service_code_description), '') AS product_or_service_code_description,

    NULLIF(TRIM(dod_claimant_program_code), '')       AS dod_claimant_program_code,
    NULLIF(TRIM(dod_claimant_program_description), '') AS dod_claimant_program_description,
    NULLIF(TRIM(dod_acquisition_program_code), '')    AS dod_acquisition_program_code,
    NULLIF(TRIM(dod_acquisition_program_description), '') AS dod_acquisition_program_description,
    NULLIF(TRIM(foreign_funding), '')                 AS foreign_funding,
    NULLIF(TRIM(foreign_funding_description), '')     AS foreign_funding_description,
    NULLIF(TRIM(country_of_product_or_service_origin), '') AS country_of_product_or_service_origin,
    NULLIF(TRIM(place_of_manufacture), '')            AS place_of_manufacture,
    NULLIF(TRIM(national_interest_action), '')        AS national_interest_action,

    NULLIF(TRIM(extent_competed), '')                 AS extent_competed,
    NULLIF(TRIM(solicitation_procedures), '')         AS solicitation_procedures,
    number_of_offers_received,
    NULLIF(TRIM(type_of_set_aside), '')               AS type_of_set_aside,
    NULLIF(TRIM(type_of_contract_pricing), '')        AS type_of_contract_pricing,
    NULLIF(TRIM(contracting_officers_determination_of_business_size), '') AS contracting_officers_determination_of_business_size,
    NULLIF(TRIM(action_type), '')                     AS action_type,

    multi_year_contract,
    woman_owned_business,
    veteran_owned_business,
    service_disabled_veteran_owned_business,
    minority_owned_business,
    c8a_program_participant,
    historically_underutilized_business_zone_hubzone_firm,
    alaskan_native_corporation_owned_firm,
    native_american_owned_business,
    educational_institution,
    nonprofit_organization
  FROM source
)
SELECT * FROM cleaned
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY contract_transaction_unique_key
  ORDER BY action_date DESC
) = 1;
