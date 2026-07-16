# Column Slice — USAspending DoD Contract Transactions

**Date:** 2026-07-14 (rev. 4) · **Status:** Draft for Day 5 data-model review
**Source file:** `FY{year}_097_Contracts_Full_*.zip` → `Contracts_PrimeTransactions` CSVs (~286–297 columns)
**Kept:** 62 columns (verified against the [USAspending Data Dictionary API](https://api.usaspending.gov/api/v2/references/data_dictionary/) **and** against a real download file on 2026-07-14)

## Why slice?

The full export has ~290 columns, most of which are administrative codes, redundant code/description pairs, or fields irrelevant to our benchmark questions. Trimming to 62 columns cuts raw size roughly 4×, keeps BigQuery storage near the free tier, and makes the data dictionary the agent relies on tractable. The original zips are preserved unmodified as the immutable raw layer (proposal §4.1).

## Kept columns and rationale

### Identity & keys (6)
| Column | Why |
|---|---|
| `contract_transaction_unique_key` | Primary key of the transaction grain; dedup/uniqueness checks |
| `contract_award_unique_key` | Groups modifications into one award — the "contract" grain; without it, contract counts are wrong |
| `award_id_piid` | Human-readable contract number (what people cite; the agent's evidence) |
| `parent_award_id_piid` | Links delivery orders to their parent contract vehicle (IDV) |
| `modification_number` | Distinguishes original awards from later modifications |
| `award_or_idv_flag` | Separates real awards from indefinite-delivery vehicles |

### Money (4)
| Column | Why |
|---|---|
| `federal_action_obligation` | Dollars obligated by *this* transaction — the core additive measure (can be negative: deobligations) |
| `total_dollars_obligated` | Running total for the award |
| `current_total_value_of_award` | Current contract ceiling |
| `potential_total_value_of_award` | Ceiling including unexercised options |

### Time (5)
| Column | Why |
|---|---|
| `action_date` | Transaction date — all trends key off this |
| `action_date_fiscal_year` | Pre-computed FY, avoids Oct–Sep math errors |
| `period_of_performance_start_date` | Contract duration analysis |
| `period_of_performance_current_end_date` | Contract duration analysis |
| `period_of_performance_potential_end_date` | End date if all options are exercised |

### Who awarded it (3)
| Column | Why |
|---|---|
| `awarding_sub_agency_name` | Army / Navy / Air Force / DISA... — the main segmentation axis (values are official names, e.g. "Department of the Army" — glossary must map "Army" → official name) |
| `awarding_office_name` | Finer-grain segmentation |
| `funding_sub_agency_name` | Who pays can differ from who awards |

**Dropped-but-verified:** `awarding_agency_name` is constant ("Department of Defense") across the entire dataset, so it is not stored. Instead, `ingest.py` **verifies it on every row during the trim** and aborts if any non-DoD row appears; the manifest records `verified_all_dod: true`. This keeps the provenance guarantee without a wasted column.

### Who won it (7)
| Column | Why |
|---|---|
| `recipient_uei` | Stable vendor identifier (names vary in spelling) |
| `recipient_name` | Vendor display name |
| `recipient_parent_uei` | Stable identifier for the parent company |
| `recipient_parent_name` | Rolls subsidiaries up to parent (Lockheed entities → Lockheed Martin) — needed for concentration metrics |
| `recipient_city_name` | Vendor city |
| `recipient_state_code` | Vendor geography |
| `recipient_country_name` | Domestic vs. foreign vendors |

### Where the work happens (4)
| Column | Why |
|---|---|
| `primary_place_of_performance_city_name` | City-level "where does the work happen?" questions |
| `primary_place_of_performance_state_code` | "Which states get the most DoD work?" |
| `primary_place_of_performance_country_name` | Overseas performance |
| `prime_award_transaction_place_of_performance_cd_current` | Congressional district (current boundaries). *Naming note:* the data dictionary still lists this as `primary_place_of_performance_congressional_district`, but real download files use the newer `_cd_current` name — discovered when the trim guard caught the mismatch on 2026-07-14. |

### What was bought (6)
| Column | Why |
|---|---|
| `award_type` | Definitive contract / delivery order / BPA... |
| `transaction_description` | Free-text description — lets the agent answer "what was this for?" |
| `naics_code` / `naics_description` | Industry classification |
| `product_or_service_code` / `product_or_service_code_description` | What was actually procured (finer than NAICS) |

### DoD programs & sourcing (9)
| Column | Why |
|---|---|
| `dod_claimant_program_code` / `dod_claimant_program_description` | DoD budget-category programs (services, electronics, aircraft...) |
| `dod_acquisition_program_code` / `dod_acquisition_program_description` | Named weapon-system / acquisition programs |
| `foreign_funding` / `foreign_funding_description` | Foreign-government-funded work (e.g., Foreign Military Sales) |
| `country_of_product_or_service_origin` | Where the product comes from |
| `place_of_manufacture` | Domestic vs. foreign manufacture (Buy American angle) |
| `national_interest_action` | Tags contracts tied to declared emergencies / contingency operations (disaster response, named operations) |

**Known limitation (observed in test data 2026-07-14):** the claimant/acquisition program fields are sparsely populated — many transactions report NULL (176 of 204 in the test slice had no claimant program). The data dictionary must state this so the agent qualifies its answers ("among transactions that report a program...").

### How it was competed (5) — feeds the competition metrics
| Column | Why |
|---|---|
| `extent_competed` | Competed vs. not competed — core of the **competition rate** metric |
| `solicitation_procedures` | How it was solicited |
| `number_of_offers_received` | Real competitiveness (1 offer ≠ competition) |
| `type_of_set_aside` | Small-business set-asides |
| `type_of_contract_pricing` | Fixed-price vs. cost-plus analysis |

### Flags (3)
| Column | Why |
|---|---|
| `contracting_officers_determination_of_business_size` | Small vs. other-than-small — **small-business participation** metric |
| `action_type` | New award vs. modification type |
| `multi_year_contract` | Multi-year contracting authority |

### Business ownership & demographics (10)
Loaded as BOOL in BigQuery (source `t`/`f`). Answers "how much went to X-owned businesses?"
| Column | Why |
|---|---|
| `woman_owned_business` | Woman-owned vendors |
| `veteran_owned_business` | Veteran-owned vendors |
| `service_disabled_veteran_owned_business` | SDVOSB — a tracked federal contracting goal |
| `minority_owned_business` | Minority-owned vendors |
| `c8a_program_participant` | SBA 8(a) disadvantaged-business program |
| `historically_underutilized_business_zone_hubzone_firm` | HUBZone firms |
| `alaskan_native_corporation_owned_firm` | ANC-owned firms (notable in DoD contracting) |
| `native_american_owned_business` | Native-American-owned vendors |
| `educational_institution` | Universities (research contracts) |
| `nonprofit_organization` | Nonprofits (FFRDCs, research orgs) |

## Metrics this slice supports

1. **Competition rate** — `extent_competed`, `number_of_offers_received`
2. **Contractor concentration (HHI)** — `recipient_parent_name`/`recipient_parent_uei`, `federal_action_obligation`
3. **Small-business participation rate** — `contracting_officers_determination_of_business_size`, `type_of_set_aside`
4. **YoY obligation growth by sub-agency** — `awarding_sub_agency_name`, `action_date_fiscal_year`
5. *(stretch)* Fixed-price share — `type_of_contract_pricing`

Metric definitions must specify handling of **negative obligations** (deobligations) — observed in real data.

## Deliberately dropped (examples)

- ~40 recipient socio-economic boolean flags (`is1862landgrantcollege`, etc.) — only `business_size` determination is needed for our metrics
- Duplicate `*_code` fields where we keep the description (or vice versa), except where the code adds join/stability value
- Treasury account / object-class fields — accounting grain, not procurement questions
- Free-text address lines, congressional district splits, legacy DUNS

Any question requiring a dropped column can be answered by re-running the trim with an expanded list — the raw zips are preserved.

## Revision history

- **rev. 4 (2026-07-14):** 50 → 62 columns. Added 10 business-ownership/demographic flags, congressional district (place of performance), and `multi_year_contract`. Considered and declined padding to 100 — remaining source columns are redundant codes, address minutiae, and admin fields; growth policy is question-driven, not count-driven. Also caught a dictionary-vs-reality naming drift on the congressional district column (see Where-the-work-happens note).
- **rev. 3 (2026-07-14):** dropped `awarding_agency_name` (constant value — now verified per-row by `ingest.py` and recorded in the manifest instead of stored); added `national_interest_action` in its place. Still 50 columns.
- **rev. 2 (2026-07-14):** 36 → 50 columns. Added at intern's request: DoD claimant + acquisition (weapon-system) programs, foreign funding, place-of-performance city, plus supporting fields (parent IDV link, award/IDV flag, potential end date, parent UEI, recipient city, product origin, place of manufacture). All 50 verified present in a real download file and loaded to `aim_raw.dod_contracts_test`.
- **rev. 1 (2026-07-14):** initial 36-column slice.
