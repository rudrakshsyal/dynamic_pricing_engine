"""Offline Gradio demo. Run: uv run python gradio_app.py."""
import gradio as gr

from src.demo_service import get_date_evidence

def show_recommendation(departure_date):
    try:
        report = get_date_evidence(departure_date.strip())
    except ValueError:
        return "Unable to read this date or its evidence.", {}
    except OSError:
        return "A required evidence file could not be loaded.", {}

    if report["status"] == "not_found":
        return "No saved recommendation for this date.", report

    if report["status"] != "ok":
        return "Evidence needs review before displaying a recommendation.", report

    rec = report["recommendation"]

    if rec["solver_status"] == "DNQ_zero_supply":
        summary = (
            "### Do not quote\n"
            "No remaining forecast capacity. "
            "The stored yield is a marker, not a selling price."
        )
    else:
        summary = (
            f"### Saved yield: USD {rec['optimal_yield']:,.0f}/EFT hour\n"
            f"- **Remaining capacity:** {rec['od_supply']:.2f} legs\n"
            f"- **Forecast enquiries:** {rec['forecasted_quotes']:.2f}\n"
            f"- **Expected bookings at this yield:** {rec['d_at_yield']:.2f}\n"
            f"- **Solver outcome:** {rec['solver_status']}"
        )

    return summary, report


with gr.Blocks(title="DPE Pricing Copilot") as demo:
    gr.Markdown(
        "# DPE Pricing Copilot\n"
        "Saved engine recommendations · Read-only · No AI calls\n\n"
        "EFT = estimated flight time. Forecasts are not guaranteed bookings."
    )

    departure_date = gr.Textbox(
        label="Departure date",
        value="2026-01-05",
        placeholder="YYYY-MM-DD",
    )
    show_button = gr.Button("View recommendation")
    summary = gr.Markdown()

    with gr.Accordion("Evidence, checks and limitations", open=False):
        evidence = gr.JSON()

    show_button.click(
        fn=show_recommendation,
        inputs=departure_date,
        outputs=[summary, evidence],
    )


if __name__ == "__main__":
    demo.launch()
