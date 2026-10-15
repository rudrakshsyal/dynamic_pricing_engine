# Synthetic fleet dataset: inventory, methodology and evaluation plan

Created October 14, 2026. No API calls and no new ML/LLM performance results. The source datasets were not changed.

## Original versus generated data

| Dataset | Calendar labels | Daily rows | Enquiry rows | Interpretation |
|---|---|---:|---:|---|
| Original | 2024-01-01 to 2025-12-31 | 731 | 47,400 | Observed historical extract |
| baseline_seed42 | 2026-01-01 to 2035-12-31 | 3,652 | 232,609 | Synthetic scenario |
| baseline_seed123 | 2026-01-01 to 2035-12-31 | 3,652 | 238,754 | Synthetic scenario |
| baseline_seed2026 | 2026-01-01 to 2035-12-31 | 3,652 | 236,493 | Synthetic scenario |
| demand_shift_seed42 | 2026-01-01 to 2035-12-31 | 3,652 | 248,881 | Synthetic scenario |
| maintenance_stress_seed42 | 2026-01-01 to 2035-12-31 | 3,652 | 232,609 | Synthetic scenario |

Each path has **3,652 days**, about five times the original daily history. The five paths contain **18,260 daily rows and 1,189,346 enquiries** in total. These paths share a generator and historical calibration; they are not 50 independent years of real evidence.

**2026–2035 are simulation calendar labels, not future forecasts.** The new paths are separate datasets, not synthetic rows silently appended to the real history.

## How generation works

1. Fit a regularized calendar regression to each of the seven daily targets using all 2024–2025 observations: weekday effects plus two annual Fourier harmonics.
2. Resample joint 28-day residual blocks, starting on matching weekdays. The same donor block supplies all seven targets and fleet size, retaining approximate short-run temporal and cross-component dependence. Add small jitter (2.5% of residual standard deviation).
3. Enforce nonnegative integer counts and availability rates in [0,1], with total unavailable fraction capped at one. Fractional rates are modeling values; they are not promised to correspond to integer aircraft counts. Fleet sizes remain within the observed 43–44 range.
4. Generate one quote row per simulated daily enquiry. Sample monthly joint histogram cells for quoted-yield bin, final-yield bin, booking indicator and lead-time bin; draw new prices inside $500 bins and leads inside seven-day bins. Preserve missing-yield categories. Do not copy quote IDs, airport routes, customer records, revenue or status histories.
5. Create three baseline paths (seeds 42, 123, 2026) and two paired stress paths (seed 42): enquiries ramp to +25% from 2033 onward; alternatively, SMX rises 8 percentage points and UMX 4 points for 60-day maintenance episodes in each of 2033–2035.

The one negative historical quote lead is floored to zero; seven-day binning also changes the exact lead-time distribution. Booking and price distributions are observational, not causal demand responses. Quote bookings are not reconciled to the flight-leg series; those come from separate calibrated processes. Jittered quoted/final yields can differ within a common bucket. No regional behavior is invented.

## Fidelity checks: baseline seed 42

| Daily component | Original mean | Synthetic mean | Original std | Synthetic std |
|---|---:|---:|---:|
| aog_rate | 0.0385 | 0.0390 | 0.0310 | 0.0292 |
| smx_rate | 0.1080 | 0.1082 | 0.0355 | 0.0344 |
| umx_rate | 0.1380 | 0.1335 | 0.0578 | 0.0570 |
| cna_rate | 0.0172 | 0.0169 | 0.0273 | 0.0230 |
| program_live_legs | 22.5308 | 22.9146 | 6.9021 | 6.9713 |
| non_program_live_legs | 7.4829 | 7.4135 | 3.2458 | 3.2199 |
| daily_quote_count | 64.8427 | 63.6936 | 33.8392 | 32.1471 |

Mean absolute change in pairwise daily correlations: **0.026**. Zero-supply proxy days: **39.7% real versus 41.4% synthetic**.
Booking rate: **8.14% versus 8.13%**. Missing quoted yields: **8.22% versus 8.21%**. Median lead: **14 versus 15 days**.

Approximate fidelity, not a perfect replica: CNA standard deviation is about 16% lower, CNA lag-one correlation falls from 0.614 to 0.519, and some longer-lag dependence weakens at block boundaries. Only two real annual cycles calibrate the seasonal shapes. Each path includes a full quality.json with quantiles, weekday/monthly-profile differences, lag-1/lag-7 correlations, missingness and booking rates. Stress paths intentionally deviate from historical averages.

Six synthetic unit tests and full-data checks passed for all five paths: reproducibility, constraints, scenario isolation, quote-count alignment, provenance, temporal splits and compatibility with existing demand-curve fitting. These checks do not certify operational realism or differential privacy.

## Longer evaluation design

Previous direct-LLM pilot: 14-day test. Later fixed-search/agent experiments: three 28-day validation periods and one 28-day final test. Two years of source history does not itself force a short horizon; the earlier windows were a small pilot.

| Stage | Simulation period | Design |
|---|---|---|
| Initial training | 2026-01-01 through 2031-12-31 | Six full simulated years |
| Validation | 2032 | Four quarterly forecast origins; test 14-, 28- and 90-day horizons |
| Final evaluation | 2033–2035 | Twelve quarterly origins; same three horizons |

The saved evaluation_plan.csv has 48 fold/horizon combinations per path: 12 validation and 36 final-test combinations. For each horizon, final windows cover 168, 336 or 1,080 distinct days respectively. Horizons overlap each other, so do not add them as independent evidence. Models refit on expanding history at each origin; later origins may use previously observed outcomes, but recipes remain frozen after validation. All three approaches must use the same cutoffs and eligible information.

## Potential impact by approach

| Approach | What this dataset can test | What it cannot establish |
|---|---|---|
| Conventional ML | Longer training histories, seasonality, lag features, learning curves and response to shifts | That extra simulated years improve forecasts on real future data |
| Direct LLM forecasting | Consistency across many origins/horizons and handling of longer history | That longer prompts improve predictions; token cost/context limits may become worse |
| LLM with tools (agent) | Adaptive model/feature selection and error investigation across scenarios | That orchestration adds value beyond extra ML search or that it discovers a true optimal price |

Yes, an LLM that plans, selects tools, reviews outcomes and changes its experiment strategy is an agent. An LLM following a fixed sequence without research discretion is a coordinator. Keep these experiment labels distinct.

## Limits and next steps

- This generator is calibrated on ALL real 2024–2025 data. Do not augment training with this version and then claim a fair evaluation on those same real dates: that would leak information. For real-data augmentation, refit the generator only on the historical training split at every cutoff.
- Additional synthetic rows resample known patterns; they do not create unobserved business regimes. The stress assumptions are deliberately chosen scenarios, not estimates of future events.
- Compare multiple seeds and report spread; never select the easiest seed. Compare real-only and synthetic-augmented training on later genuinely real data before deployment.
- Generator assumptions can favor particular forecast families. No ML-vs-LLM winner has been measured on this new dataset yet, and no revenue improvement or optimal-price truth exists here.
- Data use the existing processed-table names, and load_daily/curve fitting were checked. Existing benchmark CLI caps horizons at 31 days; the research agent also hardcodes old cutoffs and caps individual training histories at 730 days. Those controls must be parameterized before the proposed 90-day/six-year agent comparison. No paid run should use the old defaults on these paths.
- The synthetic datasets are separately archived in `experiments/synthetic_fleet_v1`. They are aggregate-derived, but there is no formal privacy guarantee.

Research context: [Synthetic data, real errors (ICML 2023)](https://arxiv.org/abs/2305.09235) explains why treating generated data as real can mislead downstream evaluation.

## Files and reproduction

Each scenario directory contains synthetic_daily.csv and data/processed/{avl_fleet_daily,legs_fleet_daily,quotes_fleet_daily,quotes_deduped_enriched}.parquet. Every generated table is labeled is_synthetic, scenario and seed. quality.json reports fidelity; events.json describes evaluator-only stress interventions. manifest.json records source/code hashes. Do not expose future event schedules to forecasting agents.

```bash
uv run python -m src.synthetic_data --root . --out /path/to/new/synthetic_fleet
```
