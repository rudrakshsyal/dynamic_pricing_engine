# Executive summary: fixed-grid AutoML

- **What changed:** added a conventional automated model-selection baseline. It ran 34 predefined component/curve trials, selected minimum validation loss, froze its choices, and refitted locally across 60 synthetic quarterly windows. No LLM or API spend; runtime approximately 5.3 minutes on this machine.
- **Supply result:** versus current ML, 90-day supply RMSE changed by −4.0%, +1.4%, −1.3%, −4.0%, and −5.6% across baseline seeds 42/123/2026, demand growth, and maintenance stress respectively. Negative is improvement. It slightly outperformed the frozen GPT choices on this metric in all five paths.
- **Pricing result:** diagnostic price error improved versus current ML in four paths and worsened on seed123. This is deviation from a simulated reference, not realized revenue or proof of an optimal price.
- **Tradeoff:** enquiry prediction error worsened in every path. No consistent improvement across every component or decision metric.
- **Interpretation:** conventional automated search is a credible baseline. These results do not establish added predictive value from the LLM coordinator, or justify replacing the production pipeline.
- **Limits:** AutoML used 34 trials versus the agent's 20 and different search spaces. The five simulated paths are related, and final scenarios had already been examined before this extension. This was not an equal-budget, untouched-holdout comparison. The simulator and current-curve reference can favor parts of the existing pipeline.

Selection: four 90-day validation folds in 2032 on seed42. Test origins: 2032-12-31 through 2035-09-30, quarterly, each followed by 90 days. Current models use all past observations; alternative daily recipes use the latest 1,095 days. Training never includes a fold's future observations. Shorter 14/28-day scores reuse the same windows' prefixes.

See [full metrics](REPORT.md) and [methodology](../../docs/AUTOML_COMPARISON.md).
