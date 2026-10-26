# Running the DPE apps

Run commands from the repository root. Both interfaces use the same evidence backend, but each has its own entry point.

| Interface | File | Command | Default local address |
|---|---|---|---|
| Gradio learning demo | `gradio_app.py` | `uv run python gradio_app.py` | http://127.0.0.1:7860 |
| Existing Streamlit app | `app.py` | `uv run streamlit run app.py` | http://localhost:8501 |

For the current learning project, use Gradio. Stop a running server with Ctrl+C in its terminal. These commands start local apps, not a hosted public deployment.

## Why the errors happened

The Gradio code was appended to the existing Streamlit app. There was no gradio_app.py, so the first command could not find it. Running python app.py then executed Streamlit outside its runner, causing missing ScriptRunContext and session-state warnings. It eventually reached the appended Gradio launch.

The repair moved the Gradio section into its own file. Both packages can coexist; no dependency removal is required. The existing dependency and lockfile changes are retained.

## Follow the flow

1. Gradio creates the date field, button and output panels.
2. Clicking View recommendation passes the date to show_recommendation.
3. That function calls src/demo_service.py, which calls EvidenceStore.explain.
4. The returned summary and evidence populate the two output panels.

The Gradio demo makes no AI calls. The existing Streamlit app has optional paid Explain/Ask actions when an API key is available; those are separate from this offline lesson.

## Check your work

Try 2026-01-05 (saved yield), 2026-01-01 (do not quote), 2026-06-01 (missing date), and an invalid date. Review changes with `git diff -- app.py` and open gradio_app.py alongside src/demo_service.py. Do not paste the Gradio app back into app.py.

## Learning checkpoint — October 26, 2026

Completed: a local Gradio screen connected to the existing evidence service. Normal recommendations, DNQ, missing dates and invalid dates were checked; the Gradio server returned HTTP 200; all six existing Streamlit app tests passed with mocked AI calls. No paid calls were made.

The demo reads saved engine outputs and reconstructs their evidence. It does not train forecasts or run a live AI agent. Charts, agent integration and public hosting remain future stages. The existing parameter-file versus notebook yield-floor discrepancy remains documented in the evidence; this UI work does not resolve it.

Git learning loop: `git status --short` shows changed files; `git diff` reviews tracked edits; `git add <files>` stages a chosen checkpoint; `git commit -m "message"` saves it locally. `git push` is a separate step to publish commits to GitHub. Dependency declarations and uv.lock are committed together so the environment can be reproduced.

Resume with `uv run python gradio_app.py`. Next lesson: build capacity and demand charts from the same report dictionary without duplicating pricing logic.
