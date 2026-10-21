# AutoML comparison

90-day supply RMSE; lower is better. Fixed-grid AutoML: 34 trials. Earlier GPT-directed selection: 20 trials. Zero new API calls.

| Scenario | Current | Agent | AutoML | AutoML vs current |
|---|---:|---:|---:|---:|
| baseline_seed42 | 4.109 | 3.991 | 3.944 | -4.0% |
| baseline_seed123 | 4.257 | 4.364 | 4.315 | +1.4% |
| baseline_seed2026 | 4.137 | 4.143 | 4.082 | -1.3% |
| demand_shift_seed42 | 4.109 | 3.991 | 3.944 | -4.0% |
| maintenance_stress_seed42 | 4.042 | 3.832 | 3.817 | -5.6% |

Price errors in comparison_results.json use a newly calculated common non-DNQ date intersection across all THREE candidates; do not compare directly with older two-way price MAEs.

Retrospective benchmark on already inspected test scenarios; unequal search spaces/budgets; not causal proof of search superiority.

## Pricing and demand diagnostics · 90 days

Price MAE is USD per estimated flight-time hour against a simulated reference, not an observed optimal price. Prices use the common non-DNQ dates across all three candidates. DNQ disagreement covers all 1,080 test dates per path; lower is better.

| Scenario | Approach | Enquiry RMSE | Price MAE | Common price dates | DNQ disagreement |
|---|---|---:|---:|---:|---:|
| Baseline seed42 | Current ML | 20.481 | $2,004 | 527 | 28.98% |
| Baseline seed42 | Frozen GPT choices | 20.481 | $1,803 | 527 | 30.46% |
| Baseline seed42 | Grid AutoML | 21.561 | $1,664 | 527 | 29.07% |
| Baseline seed123 | Current ML | 20.982 | $1,781 | 587 | 28.43% |
| Baseline seed123 | Frozen GPT choices | 20.982 | $2,059 | 587 | 28.61% |
| Baseline seed123 | Grid AutoML | 22.235 | $1,820 | 587 | 28.52% |
| Baseline seed2026 | Current ML | 20.514 | $1,959 | 547 | 28.52% |
| Baseline seed2026 | Frozen GPT choices | 20.514 | $1,963 | 547 | 28.70% |
| Baseline seed2026 | Grid AutoML | 21.755 | $1,771 | 547 | 28.33% |
| Demand growth | Current ML | 27.080 | $2,119 | 527 | 28.98% |
| Demand growth | Frozen GPT choices | 27.080 | $1,928 | 527 | 30.46% |
| Demand growth | Grid AutoML | 29.940 | $1,833 | 527 | 29.07% |
| Maintenance stress | Current ML | 20.481 | $2,175 | 419 | 36.30% |
| Maintenance stress | Frozen GPT choices | 20.481 | $1,754 | 419 | 35.00% |
| Maintenance stress | Grid AutoML | 21.561 | $1,707 | 419 | 35.28% |

AutoML has lower supply RMSE and diagnostic price MAE than current ML in four scenarios, but higher enquiry RMSE in all five. Its supply RMSE is slightly below the frozen agent in all five; this is descriptive, not a significance claim. Demand growth shares baseline seed42 capacity inputs, so their identical supply results are not independent evidence.

Verification: independently recomputed all 15 AutoML component/supply aggregates and all 45 matched three-way price MAEs from saved predictions; all passed. From repository root: `PYTHONPATH=. python experiments/automl_grid_v1/verify_metrics.py`.
