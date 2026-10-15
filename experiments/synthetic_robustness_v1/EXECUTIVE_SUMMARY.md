# Executive summary — offline robustness

**Finding: mixed gains, not a consistent win. Keep current ML as the default.**

We tested current ML versus the previously frozen GPT-5.5-selected pipeline across three synthetic seeds and two stress scenarios. No LLM calls were made; API cost was $0.

| Scenario | Change in 90-day supply RMSE (agent vs current) |
|---|---:|
| Baseline seed42 | 2.9% lower |
| Baseline seed123 | 2.5% higher |
| Baseline seed2026 | 0.1% higher |
| Demand growth, seed42 | 2.9% lower |
| Maintenance stress, seed42 | 5.2% lower |

**Method:** 60 rolling-origin tests, 12 quarterly windows per scenario, 2033–2035 simulated dates. Each forecasts 90 days; 14/28-day results are prefixes. Models use only prior history and refit at every origin. Recipes remain frozen from the earlier agent experiment. The first origin uses seven years of simulated history (2026–2032); later origins use expanding history, except ridge's fixed three-year lookback.

**Why mixed:** only the scheduled-maintenance forecast and conversion curve differ. Scheduled-maintenance RMSE itself is slightly or materially worse in every scenario, yet combined remaining-supply error sometimes improves. This demonstrates that component accuracy and clipped aggregate supply accuracy can move differently; it does not establish a causal improvement mechanism. Demand-growth supply results exactly match seed42 because that scenario changes enquiries, not capacity. It is not an independent supply-model win.

**Pricing:** the agent has lower diagnostic price deviation in seed42 and both stress scenarios, but higher deviation in seeds123/2026. Maintenance-stress deviation falls from $2,175 to $1,754 per estimated flight-time hour on 419 common eligible dates. This is not a measured revenue gain or proof of optimal prices: the reference uses realized components with current training curves, and excludes DNQ dates from price MAE. DNQ disagreement remains substantial (roughly 28–36%).

**Limits:** all simulations come from two real historical years; no fresh real data are available. Paths share the same generator, and stress scenarios share seed42. Earlier January windows are reused; the expanded test is not wholly unseen. No uncertainty/significance claim is made. No agent adapted or called tools during this run; local code refitted its previously chosen recipes.

**Next:** if comparing Gemini, use the same tool access, model-search limits and validation protocol. Freeze choices before scoring, and label these already-inspected scenarios as benchmark results—not a new untouched holdout. No Gemini calls have been made or authorized by this run.
