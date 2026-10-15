# Frozen-agent robustness results

Offline only: 0 API calls, $0 API cost. Lower errors are better.

| Path | Horizon | Current supply RMSE | Frozen agent RMSE | Change | Current price MAE | Agent price MAE | Common dates |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline_seed42 | 14 | 3.795 | 3.749 | -1.2% | 1614.28 | 1735.95 | 91 |
| baseline_seed42 | 28 | 4.001 | 3.964 | -0.9% | 1669.44 | 1707.93 | 167 |
| baseline_seed42 | 90 | 4.109 | 3.991 | -2.9% | 2003.59 | 1802.58 | 527 |
| baseline_seed123 | 14 | 4.051 | 3.973 | -1.9% | 1737.80 | 1705.28 | 90 |
| baseline_seed123 | 28 | 4.252 | 4.305 | +1.2% | 1692.95 | 1766.37 | 179 |
| baseline_seed123 | 90 | 4.257 | 4.364 | +2.5% | 1786.85 | 2066.33 | 588 |
| baseline_seed2026 | 14 | 4.326 | 4.306 | -0.5% | 2192.54 | 2123.05 | 85 |
| baseline_seed2026 | 28 | 4.341 | 4.330 | -0.3% | 1953.45 | 1956.38 | 169 |
| baseline_seed2026 | 90 | 4.137 | 4.143 | +0.1% | 1959.31 | 1962.66 | 547 |
| demand_shift_seed42 | 14 | 3.795 | 3.749 | -1.2% | 1830.28 | 1872.02 | 91 |
| demand_shift_seed42 | 28 | 4.001 | 3.964 | -0.9% | 1870.20 | 1850.41 | 167 |
| demand_shift_seed42 | 90 | 4.109 | 3.991 | -2.9% | 2118.95 | 1927.91 | 527 |
| maintenance_stress_seed42 | 14 | 3.559 | 3.281 | -7.8% | 2048.35 | 1949.43 | 68 |
| maintenance_stress_seed42 | 28 | 3.846 | 3.638 | -5.4% | 1955.59 | 1810.80 | 124 |
| maintenance_stress_seed42 | 90 | 4.042 | 3.832 | -5.2% | 2175.03 | 1754.28 | 419 |

Price MAE is deviation from a diagnostic reference using realized components and training-only current curves, not an observed optimal price or revenue. It favors the current curve construction by design. Common non-DNQ dates match between candidates within each path/horizon, not necessarily across paths.

Twelve quarterly origins per path, 2032-12-31 through 2035-09-30; 90 days each (1,080 days per path). The 14/28-day scores are overlapping prefixes, not additional independent tests. Models refit using only observations available at each origin. Ridge uses its frozen 1,095-day window; current recipes use all prior history.

Agent choices were selected previously on baseline seed42 validation windows in 2032. This measures transfer of those fixed choices, not a newly adapting agent. Three baseline seeds and two paired seed42 stress scenarios are related simulations calibrated from the same two real years. No confidence or real-world revenue claim is established. No fresh real data are available; Gemini remains untested.
