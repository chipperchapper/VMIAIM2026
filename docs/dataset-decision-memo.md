# Dataset Decision Memo

**Project:** Hosted Analytics Agent (two-week intern project)
**Status:** ✅ DECIDED 2026-07-14 — Candidate A selected: USAspending DoD contracts, two fiscal years (FY2024–FY2025, ~2.2 GB zipped)

## Purpose

The project proposal requires comparing at least three candidate datasets before implementation begins. This memo compares three candidates, scores them against the proposal's selection rubric, and recommends one. All sizes and licenses were verified against the live sources on 2026-07-13.

## Candidates

### A. USAspending.gov — DoD Contract Awards
Every Department of Defense contract transaction, published by the US Treasury. ~1.1 GB zipped (~6–8 GB raw) **per fiscal year**; archives cover FY2008–present; 200+ columns per record. US Government work — public domain, no license restrictions.
*Sample questions:* "Which contractors received the most Navy dollars in FY2025?" · "What share of awards were competitively bid?"
*Metric ideas:* contractor concentration index (HHI), competition rate (competed vs. sole-source), award growth by service branch, small-business participation rate.

### B. Amazon Reviews 2023 — Video Games category (McAuley Lab, UC San Diego)
Real Amazon review data published by an academic research lab: ~4.6M reviews of ~137k video-game products, 1996–2023. Downloads as two related gzipped JSONL files — reviews (rating, text, verified purchase, helpful votes, second-level timestamps) and item metadata (title, price, store, category tree, average rating) — ~0.9 GB compressed for the category. Normalizes naturally into products, stores, users, and reviews tables. Larger slices available (Toys & Games ~1.9 GB, Electronics ~6.5 GB). License: **none formally specified** — released for research use with a cite-the-paper convention; universally used in academia but flagged for sponsor awareness.
*Sample questions:* "Did ratings for this game drop after launch month?" · "Which stores sell the highest-rated products under $20?"
*Metric ideas:* Bayesian-weighted product rating, verified-purchase ratio, review helpfulness index, price-vs-rating value score.

### C. Bureau of Transportation Statistics — Airline On-Time Performance
Every US domestic flight since 1987: carrier, route, schedule, delays by cause, cancellations. ~30 MB zipped (~250 MB raw) per month; ~7M flights/year; updated monthly. US Government work — public domain. Ships as one wide fact table (~110 columns) that we would normalize into carrier/airport/route dimensions.
*Sample questions:* "Which airline was most reliable into Denver last winter?" · "Are weather delays getting worse?"
*Metric ideas:* reliability score (weighted on-time %), delay-cause breakdown, seasonal delay index, route-level cancellation rate.

## Rubric comparison

| Criterion (from proposal §2.1) | A. DoD Contracts | B. Amazon Reviews | C. Flights |
|---|---|---|---|
| Legal & accessible | ✅ Public domain | ⚠️ No formal license (research-use convention) | ✅ Public domain |
| Analytically rich | ✅ Very rich | ✅ Very rich (text + numeric + time) | ✅ Rich |
| Sufficient scale | ✅ Largest (GBs) | ✅ Large (~0.9 GB/category, scalable) | ✅ Large (scalable by months) |
| Documentable | ⚠️ Official dictionary exists but 200+ messy columns | ✅ Well-documented research release | ✅ Excellent official docs |
| Modelable (multi-entity) | ✅ Vendors, agencies, awards, places | ✅ Products, stores, users, reviews | ⚠️ One fact table; dimensions must be built |
| Metric potential | ✅ Strong, nontrivial | ✅ Strong (weighted ratings are nicely nontrivial) | ✅ Strong, intuitive |
| Low sensitivity | ✅ Public records | ✅ Anonymized user IDs; public review text | ✅ No personal data |
| Feasible in 2 weeks | ⚠️ **Highest risk** — must slice years/columns | ✅ Moderate — JSONL needs normalization | ✅ Moderate — pick months to ingest |

## Recommendation

**Primary: A — USAspending DoD contracts, deliberately sliced.** Ingest **two fiscal years (FY2024–FY2025, ~2.2 GB zipped — final decision 2026-07-14)** and keep ~30–40 analytically useful columns out of 200+. This is the only candidate where a cloud warehouse (BigQuery) genuinely earns its place, the domain is engaging, the license is unrestricted, and "which vendors, which agencies, how competed" questions demo exactly like a real internal analytics agent. The slicing decision itself becomes documented modeling work (proposal §4.1 requires recording any filtering performed).

**Risk and fallback:** the main risk is ingestion/cleaning time on messy government data. If raw data is not loaded and queryable by end of Day 4 (per the work plan), fall back to **C — BTS Flights** (2–3 years of months), which offers similar scale with far cleaner files and the same architecture. **B — Amazon Reviews** is the most engaging demo of the three, but its lack of a formal license makes it the weakest choice to standardize on if this pattern is later reused internally; it remains a strong option if the sponsor is comfortable with research-use terms.

## Sponsor questions (Day 2 checkpoint)

1. Approve the primary choice and the FY2024–2025 / ~35-column slice?
2. Any concern demoing on US defense spending data?
3. Confirm the Day-4 fallback trigger is acceptable.
4. If the Amazon option is preferred instead: is a research-use dataset with no formal license acceptable for this internal demo?

## Source verification log (2026-07-13)

- DoD FY2025 full archive: `files.usaspending.gov/award_data_archive/FY2025_097_Contracts_Full_20260706.zip` — 1,130,913,708 bytes (FY2023/FY2024 similar)
- Amazon Reviews 2023 Video Games: `mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Video_Games.jsonl.gz` — 814,206,092 bytes; metadata file — 103,096,082 bytes; no license stated on `amazon-reviews-2023.github.io`
- BTS on-time June 2025: `transtats.bts.gov/PREZIP/...2025_6.zip` — 31,131,411 bytes
