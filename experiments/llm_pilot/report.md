# Forecast benchmark

LLM results: completed

Retrospective rolling-origin test. Lower MAE/RMSE is better. Pricing reference is NOT an optimal-price label.

| Origin | Candidate | Target | MAE | RMSE |
|---|---|---|---:|---:|
| 2025-11-30 | current_refit | aog_rate | 0.0282 | 0.0319 |
| 2025-11-30 | current_refit | smx_rate | 0.0110 | 0.0143 |
| 2025-11-30 | current_refit | umx_rate | 0.0492 | 0.0585 |
| 2025-11-30 | current_refit | cna_rate | 0.0159 | 0.0164 |
| 2025-11-30 | current_refit | program_live_legs | 5.1064 | 5.6469 |
| 2025-11-30 | current_refit | non_program_live_legs | 2.2367 | 2.4362 |
| 2025-11-30 | current_refit | daily_quote_count | 14.7382 | 17.2151 |
| 2025-11-30 | current_refit | remaining_supply_proxy | 1.9796 | 3.1504 |
| 2025-11-30 | seasonal_naive | aog_rate | 0.0515 | 0.0667 |
| 2025-11-30 | seasonal_naive | smx_rate | 0.0532 | 0.0590 |
| 2025-11-30 | seasonal_naive | umx_rate | 0.0781 | 0.0881 |
| 2025-11-30 | seasonal_naive | cna_rate | 0.0166 | 0.0233 |
| 2025-11-30 | seasonal_naive | program_live_legs | 14.1429 | 16.6819 |
| 2025-11-30 | seasonal_naive | non_program_live_legs | 3.2857 | 3.9461 |
| 2025-11-30 | seasonal_naive | daily_quote_count | 17.0000 | 23.2010 |
| 2025-11-30 | seasonal_naive | remaining_supply_proxy | 7.4000 | 10.1638 |
| 2025-11-30 | llm_forecasts_current_curves | aog_rate | 0.0415 | 0.0516 |
| 2025-11-30 | llm_forecasts_current_curves | smx_rate | 0.0166 | 0.0215 |
| 2025-11-30 | llm_forecasts_current_curves | umx_rate | 0.0581 | 0.0754 |
| 2025-11-30 | llm_forecasts_current_curves | cna_rate | 0.0133 | 0.0176 |
| 2025-11-30 | llm_forecasts_current_curves | program_live_legs | 6.6429 | 7.2752 |
| 2025-11-30 | llm_forecasts_current_curves | non_program_live_legs | 1.9286 | 2.2200 |
| 2025-11-30 | llm_forecasts_current_curves | daily_quote_count | 14.2857 | 17.2420 |
| 2025-11-30 | llm_forecasts_current_curves | remaining_supply_proxy | 2.6371 | 3.9925 |
| 2025-11-30 | current_forecasts_llm_curves | aog_rate | 0.0282 | 0.0319 |
| 2025-11-30 | current_forecasts_llm_curves | smx_rate | 0.0110 | 0.0143 |
| 2025-11-30 | current_forecasts_llm_curves | umx_rate | 0.0492 | 0.0585 |
| 2025-11-30 | current_forecasts_llm_curves | cna_rate | 0.0159 | 0.0164 |
| 2025-11-30 | current_forecasts_llm_curves | program_live_legs | 5.1064 | 5.6469 |
| 2025-11-30 | current_forecasts_llm_curves | non_program_live_legs | 2.2367 | 2.4362 |
| 2025-11-30 | current_forecasts_llm_curves | daily_quote_count | 14.7382 | 17.2151 |
| 2025-11-30 | current_forecasts_llm_curves | remaining_supply_proxy | 1.9796 | 3.1504 |
| 2025-11-30 | llm_full | aog_rate | 0.0415 | 0.0516 |
| 2025-11-30 | llm_full | smx_rate | 0.0166 | 0.0215 |
| 2025-11-30 | llm_full | umx_rate | 0.0581 | 0.0754 |
| 2025-11-30 | llm_full | cna_rate | 0.0133 | 0.0176 |
| 2025-11-30 | llm_full | program_live_legs | 6.6429 | 7.2752 |
| 2025-11-30 | llm_full | non_program_live_legs | 1.9286 | 2.2200 |
| 2025-11-30 | llm_full | daily_quote_count | 14.2857 | 17.2420 |
| 2025-11-30 | llm_full | remaining_supply_proxy | 2.6371 | 3.9925 |

No revenue winner established. Compare the same folds only; invalid LLM folds are reported, not replaced.
Limitations: current recipes were developed using these historical years; this is not an untouched final holdout. Final booking outcomes use departure maturity as a proxy for availability. Final yield can contain realized revenue. Conversion scores are observational and selected by yield availability. No causal elasticity or revenue uplift is established. Historical processed tables are not archived as-of snapshots. Pricing uses a fixed 1.06 legs/tail, origin fleet size, zero separate OD adjustment, and the existing enquiry/departure-date join.

## Aggregate forecast errors

| Candidate | Target | Days | MAE | RMSE |
|---|---|---:|---:|---:|
| current_forecasts_llm_curves | aog_rate | 14 | 0.0282 | 0.0319 |
| current_forecasts_llm_curves | smx_rate | 14 | 0.0110 | 0.0143 |
| current_forecasts_llm_curves | umx_rate | 14 | 0.0492 | 0.0585 |
| current_forecasts_llm_curves | cna_rate | 14 | 0.0159 | 0.0164 |
| current_forecasts_llm_curves | program_live_legs | 14 | 5.1064 | 5.6469 |
| current_forecasts_llm_curves | non_program_live_legs | 14 | 2.2367 | 2.4362 |
| current_forecasts_llm_curves | daily_quote_count | 14 | 14.7382 | 17.2151 |
| current_forecasts_llm_curves | remaining_supply_proxy | 14 | 1.9796 | 3.1504 |
| current_refit | aog_rate | 14 | 0.0282 | 0.0319 |
| current_refit | smx_rate | 14 | 0.0110 | 0.0143 |
| current_refit | umx_rate | 14 | 0.0492 | 0.0585 |
| current_refit | cna_rate | 14 | 0.0159 | 0.0164 |
| current_refit | program_live_legs | 14 | 5.1064 | 5.6469 |
| current_refit | non_program_live_legs | 14 | 2.2367 | 2.4362 |
| current_refit | daily_quote_count | 14 | 14.7382 | 17.2151 |
| current_refit | remaining_supply_proxy | 14 | 1.9796 | 3.1504 |
| llm_forecasts_current_curves | aog_rate | 14 | 0.0415 | 0.0516 |
| llm_forecasts_current_curves | smx_rate | 14 | 0.0166 | 0.0215 |
| llm_forecasts_current_curves | umx_rate | 14 | 0.0581 | 0.0754 |
| llm_forecasts_current_curves | cna_rate | 14 | 0.0133 | 0.0176 |
| llm_forecasts_current_curves | program_live_legs | 14 | 6.6429 | 7.2752 |
| llm_forecasts_current_curves | non_program_live_legs | 14 | 1.9286 | 2.2200 |
| llm_forecasts_current_curves | daily_quote_count | 14 | 14.2857 | 17.2420 |
| llm_forecasts_current_curves | remaining_supply_proxy | 14 | 2.6371 | 3.9925 |
| llm_full | aog_rate | 14 | 0.0415 | 0.0516 |
| llm_full | smx_rate | 14 | 0.0166 | 0.0215 |
| llm_full | umx_rate | 14 | 0.0581 | 0.0754 |
| llm_full | cna_rate | 14 | 0.0133 | 0.0176 |
| llm_full | program_live_legs | 14 | 6.6429 | 7.2752 |
| llm_full | non_program_live_legs | 14 | 1.9286 | 2.2200 |
| llm_full | daily_quote_count | 14 | 14.2857 | 17.2420 |
| llm_full | remaining_supply_proxy | 14 | 2.6371 | 3.9925 |
| seasonal_naive | aog_rate | 14 | 0.0515 | 0.0667 |
| seasonal_naive | smx_rate | 14 | 0.0532 | 0.0590 |
| seasonal_naive | umx_rate | 14 | 0.0781 | 0.0881 |
| seasonal_naive | cna_rate | 14 | 0.0166 | 0.0233 |
| seasonal_naive | program_live_legs | 14 | 14.1429 | 16.6819 |
| seasonal_naive | non_program_live_legs | 14 | 3.2857 | 3.9461 |
| seasonal_naive | daily_quote_count | 14 | 17.0000 | 23.2010 |
| seasonal_naive | remaining_supply_proxy | 14 | 7.4000 | 10.1638 |
