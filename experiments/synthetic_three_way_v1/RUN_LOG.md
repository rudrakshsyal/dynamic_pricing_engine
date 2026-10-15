# Synthetic comparison activity log

1. User approved a new $4 cap for baseline_seed42 only.
2. Pushed the synthetic generator and all five datasets separately in commit b174652.
3. Declared four 90-day validation origins and three final origins; shorter horizons are prefixes.
4. Computed current-engine predictions offline before paid calls.
5. Added long-history eligibility and strict direct-output validation; 33 relevant offline tests passed.
6. Started GPT-5.5 research with batched trials and one shared $4 ledger for agent plus direct calls. No final scores are supplied to the agent.

7. Agent finished 20 trials and froze nine choices before final scoring; no ensembles used.
8. Completed all three direct calls and all 90-day output arrays passed validation.
9. Independent local scoring completed for 14, 28 and 90-day prefixes; current engine had lowest supply/diagnostic price error at all horizons.
10. Final conservative cost $2.143795 under $4; no further paid calls.
11. Independently recomputed pooled forecast RMSE and decision agreement from saved rows; confirmed identical price-date counts within each horizon.
12. Recorded limitations including synthetic-generator dependence, one seed, implicit calendar encoding and different reasoning settings.
