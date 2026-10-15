# Agent-designed pipeline vs current engine

Retrospective November 1–28, 2025 test. Choices frozen before scoring. No revenue uplift measured.

| Component | Current RMSE | Agent-selected RMSE | Error reduction |
|---|---:|---:|---:|
| aog_rate | 0.03847 | 0.03377 | 12.2% |
| smx_rate | 0.06084 | 0.06084 | 0.0% |
| umx_rate | 0.03035 | 0.03968 | -30.7% |
| cna_rate | 0.01737 | 0.01243 | 28.4% |
| program_live_legs | 7.04035 | 7.04035 | 0.0% |
| non_program_live_legs | 2.75031 | 3.11725 | -13.3% |
| daily_quote_count | 21.89147 | 21.89147 | 0.0% |
| remaining_supply_proxy | 6.05565 | 6.20180 | -2.4% |

| Pipeline | Status agreement | DNQ disagreement | Same-date price MAE | N |
|---|---:|---:|---:|---:|
| current | 17.9% | 60.7% | 2074.7200686399806 | 6 |
| agent_forecasts | 21.4% | 67.9% | 3037.031404233289 | 6 |
| agent_full | 21.4% | 67.9% | 2995.0289639314274 | 6 |

Positive reduction means better forecasts. The price reference uses actual daily inputs with the current train-only demand curve, not true optimal-price labels.
Comparison measures the entire adaptive search pipeline against fixed current recipes. It does not isolate the benefit of an LLM from extra tuning or compute.
See frozen_choices.json for agent reasons, trials.json for all experiments and audit.jsonl for tool activity.
