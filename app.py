"""Local, read-only pricing explanation UI. Start with streamlit run app.py."""
from html import escape
import altair as alt
import pandas as pd
import json
import os
from pathlib import Path

import streamlit as st

from src.rca_agent import explain_with_agent, explanation_error_message
from src.rca_evidence import EvidenceStore, ROOT
from src.rca_chat import ask_about_date
from src.agent_runtime import run_agent

st.set_page_config(page_title="DPE | Explain a price", page_icon="✈", layout="wide")
st.markdown("""<style>
.block-container {max-width:1200px;padding-top:2.5rem;}
h1 {font-size:2.2rem !important;letter-spacing:-.04em;}
[data-testid="stMetric"] {padding:16px;border:1px solid #64748b44;border-radius:14px;}
[data-testid="stMetricValue"] {font-size:1.7rem;}
.brief {padding:20px 24px;border-left:4px solid #38bdf8;background:#38bdf811;border-radius:12px;margin:16px 0 22px;}
.brief small {color:#38bdf8;letter-spacing:.1em;font-weight:700;}
.brief p {font-size:1.2rem;margin:8px 0 0;line-height:1.5;}
.insight {border:1px solid #64748b44;border-radius:12px;padding:18px;min-height:130px;}
.insight small {color:#38bdf8;font-weight:700;}
.insight p {line-height:1.5;margin:8px 0 0;}
</style>""", unsafe_allow_html=True)
st.title("Pricing intelligence")
st.caption("NREG Challenger fleet · Saved recommendations · Read-only")

with st.sidebar:
    st.header("Explanation settings")
    model = st.text_input("OpenAI model", value="gpt-5.5").strip()
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    st.caption("API key available" if has_key else "Set OPENAI_API_KEY in the terminal before launching.")
    st.caption("AI calls occur on Explain or Ask, with up to one correction attempt. The selected date’s evidence is sent to OpenAI.")
    st.caption("Chat answers use this date’s evidence. Questions are not sent to the data team.")

try:
    store = EvidenceStore(Path(os.environ.get("DPE_REPO_ROOT", str(ROOT))))
    dates = sorted({str(d)[:10] for d in store.tables["recommendation"]["date"].to_list() if d is not None})
    if not dates:
        st.warning("No saved recommendations are available.")
        st.stop()
    selected = st.selectbox("Departure date", dates, index=dates.index("2026-01-05") if "2026-01-05" in dates else 0)
    report = store.explain(selected)
except (OSError, ValueError, KeyError, TypeError):
    st.error("Saved evidence could not be loaded. Check the data files and run the offline CLI for diagnostics.")
    st.stop()

if report["status"] != "ok":
    st.error("This recommendation needs a data review. AI explanation is unavailable until the evidence checks pass.")
    with st.expander("Review details", expanded=True):
        st.json(report)
    st.stop()

rec = report["recommendation"]
supply = report["supply"]
status_labels = {"solved": "Balanced", "DNQ_zero_supply": "Do not quote",
                 "demand_below_floor": "Price floor", "demand_above_ceiling": "Price ceiling"}
dnq = rec["solver_status"] == "DNQ_zero_supply"
a, b, c, d = st.columns(4)
a.metric("Recommendation", "Do not quote" if dnq else f"${rec['optimal_yield']:,.0f}")
a.caption("No sellable capacity forecast" if dnq else "per estimated flight-time hour")
b.metric("Remaining capacity", f"{rec['od_supply']:.2f} legs")
c.metric("Forecast enquiries", f"{rec['forecasted_quotes']:.2f}")
d.metric("Decision", status_labels.get(rec["solver_status"], "Review required"))
if dnq:
    st.info("The saved $15,000 value is a do-not-quote marker, not a selling price.")

points = report["demand"]["points"]
if dnq:
    takeaway = "Do not quote: no remaining capacity is forecast."
elif rec["solver_status"] == "solved":
    takeaway = f"${rec['optimal_yield']:,.0f} per estimated flight-time hour balances forecast demand with remaining capacity."
elif rec["solver_status"] == "demand_below_floor":
    takeaway = "Price floor selected: forecast demand remains below capacity."
else:
    takeaway = "Price ceiling selected: forecast demand still exceeds capacity."
st.markdown(f'<div class="brief"><small>PRICING DECISION</small><p>{escape(takeaway)}</p></div>', unsafe_allow_html=True)
left, right = st.columns(2, gap="large")
with left:
    st.subheader("Available capacity")
    raw = supply["raw_leg_supply_fc"]
    balance = raw
    bars = [{"Stage": "Raw", "Start": 0., "End": raw, "Change": raw, "Kind": "Capacity"}]
    for label, key in [("Program", "program_live_legs_fc"), ("Non-program", "non_program_live_legs_fc"), ("OD adjustment", "current_od_adjusted")]:
        next_balance = balance - supply[key]
        bars.append({"Stage": label, "Start": next_balance, "End": balance, "Change": -supply[key], "Kind": "Consumed"})
        balance = next_balance
    bars.append({"Stage": "Remaining", "Start": 0., "End": supply["reconstructed_supply"], "Change": supply["reconstructed_supply"], "Kind": "Remaining"})
    base = alt.Chart(pd.DataFrame(bars)).encode(x=alt.X("Stage:N", sort=[b["Stage"] for b in bars], axis=alt.Axis(labelAngle=0, title=None)))
    chart = base.mark_bar(size=38, cornerRadius=3).encode(y=alt.Y("Start:Q", title="Forecast legs"), y2="End:Q", color=alt.Color("Kind:N", scale=alt.Scale(domain=["Capacity", "Consumed", "Remaining"], range=["#94a3b8", "#f59e0b", "#38bdf8"]), legend=None), tooltip=["Stage", alt.Tooltip("Change:Q", format=".2f")])
    st.altair_chart(chart.properties(height=250), width="stretch")
    st.caption(f"{supply['reconstructed_supply']:.2f} legs remaining after forecast consumption.")
with right:
    st.subheader("Demand at each price")
    rows = [{"Evaluation": name.title() if not (dnq and name == "selected") else "DNQ marker", "Yield": p["yield"], "Bookings": p["expected_bookings"]} for name, p in points.items()]
    chart = alt.Chart(pd.DataFrame(rows)).mark_circle(size=150).encode(x=alt.X("Yield:Q", title="Yield · USD / EFT hour", scale=alt.Scale(zero=False), axis=alt.Axis(format=",.0f")), y=alt.Y("Bookings:Q", title="Bookings / legs", scale=alt.Scale(zero=True)), color=alt.Color("Evaluation:N", scale=alt.Scale(range=["#94a3b8", "#38bdf8", "#f59e0b"]), legend=alt.Legend(orient="bottom")), tooltip=["Evaluation", alt.Tooltip("Yield:Q", format=",.0f"), alt.Tooltip("Bookings:Q", format=".4f")])
    capacity = alt.Chart(pd.DataFrame([{"Capacity": rec["od_supply"]}])).mark_rule(color="#38bdf8", strokeDash=[5,5]).encode(y="Capacity:Q", tooltip=[alt.Tooltip("Capacity:Q", format=".2f")])
    st.altair_chart((chart + capacity).properties(height=250), width="stretch")
    st.caption("Dots: expected bookings. Dashed line: available legs." if not dnq else "No selling price. Dots show model demand only.")
st.caption("Based on saved forecasts. Assumptions and limitations below.")

request_key = (selected, report["snapshot_id"], model, "runtime-v5")
if st.session_state.get("active_request") != request_key:
    st.session_state["active_request"] = request_key
    st.session_state["date_chat"] = []
    st.session_state.pop("narrative", None)
    st.session_state.pop("explanation_error", None)

if st.button("Explain", type="primary", disabled=not has_key or not model):
    st.session_state.pop("narrative", None)
    st.session_state.pop("explanation_error", None)
    try:
        with st.spinner("Reading supply, demand and solver evidence…"):
            st.session_state["narrative"] = run_agent(explain_with_agent(report, model))
    except Exception as exc:
        # Never render raw provider errors, credentials, or stack traces in the UI.
        st.session_state["explanation_error"] = explanation_error_message(exc)

if st.session_state.get("explanation_error"):
    st.error(st.session_state["explanation_error"])
narrative = st.session_state.get("narrative")
if narrative:
    st.subheader("Revenue brief")
    cards = st.columns(min(3, len(narrative["explanation"]["findings"])))
    for index, finding in enumerate(narrative["explanation"]["findings"][:3]):
        with cards[index]:
            st.markdown(f'<div class="insight"><small>{["DECISION", "CAPACITY", "DEMAND"][index]}</small><p>{escape(finding["explanation"])}</p></div>', unsafe_allow_html=True)
    with st.expander("Sources & data-team questions"):
        for finding in narrative["explanation"]["findings"]:
            st.text(finding["explanation"])
            st.table([{"Evidence": ref, "Value": f"{report['facts'][ref]:,.4f}" if isinstance(report["facts"][ref], float) else str(report["facts"][ref])} for ref in finding["evidence_refs"]])
        for question in narrative["explanation"]["unresolved_questions"]:
            st.text(question)
        st.caption("AI-generated interpretation; references checked. Questions are drafts, not sent.")
else:
    st.caption("Explain adds a short revenue brief.")

with st.expander("Ask about this date", expanded=False):
    st.caption("Read-only · Last four exchanges used as context · Each question makes an AI call.")
    if st.button("Clear chat"):
        st.session_state["date_chat"] = []
    with st.form("date_question", clear_on_submit=True):
        question = st.text_input("Your question", placeholder="Why is capacity limited on this date?", max_chars=1000)
        send = st.form_submit_button("Ask", disabled=not has_key or not model)
    if send and question.strip():
        try:
            with st.spinner("Checking this date’s evidence…"):
                response = run_agent(ask_about_date(report, question, st.session_state.get("date_chat", []), model))
            st.session_state.setdefault("date_chat", []).append({"question": question, "response": response})
        except Exception as exc:
            st.error(explanation_error_message(exc))
    for exchange in st.session_state.get("date_chat", []):
        with st.chat_message("user"):
            st.text(exchange["question"])
        with st.chat_message("assistant"):
            answer = exchange["response"]
            st.text(answer["answer"])
            if answer["status"] == "needs_data":
                st.caption("For the data team · draft only, not sent")
                st.text(answer["data_team_question"])
            if answer["evidence_refs"]:
                with st.expander("Answer sources"):
                    for ref in answer["evidence_refs"]:
                        st.text(f"{ref}: {report['notes'] if ref == 'limitations' else report['facts'][ref]}")
    st.caption("AI interpretation; citation checks do not prove every claim is correct.")

st.divider()
with st.expander("Supply calculation"):
    st.table([
        {"Component": "Raw capacity", "Legs": supply["raw_leg_supply_fc"]},
        {"Component": "Less program consumption", "Legs": -supply["program_live_legs_fc"]},
        {"Component": "Less non-program consumption (currently includes OD)", "Legs": -supply["non_program_live_legs_fc"]},
        {"Component": "Less adjusted existing OD bookings", "Legs": -supply["current_od_adjusted"]},
        {"Component": "Balance before clipping", "Legs": supply["balance_before_clipping"]},
        {"Component": "Remaining after clipping at zero", "Legs": supply["reconstructed_supply"]},
    ])
with st.expander("Demand and solver calculation"):
    st.write(report["solver"]["reason"])
    st.table([{"Evaluation": name, "Yield ($/EFT hour)": p["yield"],
               "Expected bookings": p["expected_bookings"],
               "Quote multiplier": p["quote_multiplier"],
               "Conversion probability": p["conversion_probability"]}
              for name, p in report["demand"]["points"].items()])
    if dnq:
        st.caption("Demand at the marker yield is a diagnostic reconstruction. The saved DNQ row sets demand to zero.")
with st.expander("Checks and limitations"):
    st.caption("Passing checks means the saved numbers reconcile; it does not validate the forecasting models.")
    st.table([{"Check": key, "Result": "Pass" if value else "Fail"} for key, value in report["checks"].items()])
    for note in report["notes"]:
        st.text("• " + note)
with st.expander("Evidence snapshot and tool activity"):
    st.code(report["snapshot_id"], language=None)
    st.json(report["sources"])
    if narrative:
        st.write("Tools called: " + ", ".join(narrative["tool_calls"]))

st.download_button("Download evidence JSON", json.dumps(report, indent=2, allow_nan=False),
                   file_name=f"dpe-evidence-{selected}.json", mime="application/json")
