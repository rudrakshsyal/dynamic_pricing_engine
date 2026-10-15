# Three-way synthetic baseline pilot

Completed with $2.143795 conservatively accounted under a new $4 cap.
Dataset: baseline_seed42. Four 90-day validation windows in 2032; three annual-origin 90-day final windows in 2033–2035. Shorter horizons are prefixes of the SAME forecasts.
These are synthetic calendar labels, not future forecasts. No real-world revenue or optimal-price improvement is established.

| Horizon | Approach | Supply RMSE | Status agreement | DNQ disagreement | Same-date price MAE | Price dates |
|---|---|---:|---:|---:|---:|---:|
| 14 | current | 2.999 | 45.2% | 21.4% | 1744.82 | 20 |
| 14 | direct_llm | 5.642 | 28.6% | 47.6% | 2534.67 | 20 |
| 14 | agent | 3.250 | 47.6% | 23.8% | 2411.84 | 20 |
| 28 | current | 4.239 | 44.0% | 26.2% | 1945.47 | 43 |
| 28 | direct_llm | 5.858 | 27.4% | 41.7% | 2885.31 | 43 |
| 28 | agent | 4.369 | 42.9% | 29.8% | 2299.86 | 43 |
| 90 | current | 3.594 | 51.1% | 31.1% | 2090.56 | 52 |
| 90 | direct_llm | 4.696 | 37.0% | 46.7% | 3337.07 | 52 |
| 90 | agent | 3.634 | 51.1% | 33.0% | 2297.39 | 52 |

## Primary 90-day component results

| Component | Current RMSE | Direct LLM RMSE | Agent RMSE |
|---|---:|---:|---:|
| aog_rate | 0.02609 | 0.03597 | 0.02609 |
| smx_rate | 0.02926 | 0.03952 | 0.02863 |
| umx_rate | 0.05230 | 0.07676 | 0.05230 |
| cna_rate | 0.02374 | 0.02746 | 0.02374 |
| program_live_legs | 5.89750 | 9.74858 | 5.89750 |
| non_program_live_legs | 2.83497 | 4.24446 | 2.83497 |
| daily_quote_count | 17.69011 | 50.76609 | 17.69011 |

Current means the existing Prophet/seasonal recipes. The direct LLM receives all chronological training rows (rates rounded to 4 decimals) plus historical curve bins. The agent sees training summaries and validation scores; its tools train on the available history using agent-chosen history windows.
The generator was calibrated on all real 2024–2025 data. This test measures performance inside that simulator, not independent real-world generalization. Only one seed was tested. Horizons overlap and are not independent observations.
Price comparison uses the identical intersection of non-DNQ dates across all three approaches and the diagnostic reference. Predictions outside the common set still contribute to status/DNQ metrics. More accurate forecasts do not by themselves establish higher revenue.
