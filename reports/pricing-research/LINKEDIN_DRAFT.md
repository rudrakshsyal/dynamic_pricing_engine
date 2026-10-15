# LinkedIn draft — not published

Can an LLM improve a dynamic pricing engine—or is it more useful directing the experiments?

I compared three approaches: traditional ML forecasts, direct GPT-5.5 forecasts, and GPT-5.5 choosing and evaluating ML models through tools. All fed the same deterministic supply–demand pricing solver.

The results challenged the assumption that adding an LLM automatically improves predictions:

- In one synthetic pilot, direct LLM forecasts had 30.7% higher 90-day remaining-supply RMSE than current ML.
- Across 60 quarterly robustness windows, the frozen agent-selected pipeline showed mixed results: 5.2% lower supply error under maintenance stress, but 2.5% higher error on another baseline seed.
- Conventional model search also showed tradeoffs: improved supply error did not necessarily improve zero-capacity decisions.

My takeaway: agentic experimentation can automate research decisions, but it still needs disciplined validation and a well-chosen objective. Component-level improvements do not guarantee better pricing.

These are historical and synthetic benchmark results—not evidence of revenue uplift. Synthetic data expanded stress coverage; it did not create new real-world evidence.

I built an interactive report covering the methods, test windows, results, and limitations. The next question is how to align model selection with downstream decisions—not just forecast accuracy.

#MachineLearning #AgenticAI #DynamicPricing #Forecasting
