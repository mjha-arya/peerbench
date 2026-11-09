"""PeerBench Streamlit UI. Run from the PeerBench folder:  streamlit run app.py"""
import json
from pathlib import Path

import streamlit as st

from peerbench import config
from peerbench.metrics import BadCSV, load_csv, money, p, summarise

SAMPLE = "year,revenue,cogs,opex,net_income\n2023,10000000,4000000,5000000,1000000\n2024,14000000,5600000,6500000,1900000\n"

STEPS = {
    "load_csv": "Read the CSV",
    "compute_metrics": "Compute your metrics (code)",
    "resolve_peers": "Resolve competitor tickers",
    "fetch_peer_financials": "Fetch peer financials (Yahoo Finance)",
    "research_context": "Search web context (Tavily)",
    "write_report": "Write draft",
    "check_numbers": "Verify every number (code)",
    "critique": "Critic review",
    "research_critique": "Research the critic's points",
    "finalize": "Render report",
}

st.set_page_config(page_title="PeerBench", page_icon="📊", layout="wide")
st.title("PeerBench")
st.caption("Your P&L vs listed competitors: every number is computed in code and verified before it reaches the report.")

with st.sidebar:
    st.header("Inputs")
    company = st.text_input("Company name", "Mega AI Co")
    competitors = st.text_area("Competitors (one per line)", "Datadog\nElastic", height=110)
    max_rev = st.slider("Max revisions", 1, 3, 2)
    upload = st.file_uploader("Financials CSV", type="csv",
                              help="Columns: year, revenue, cogs, net_income (opex optional)")
    use_sample = st.checkbox("Use sample CSV instead", value=upload is None)
    st.download_button("Download sample CSV", SAMPLE, "financials-sample.csv", "text/csv")
    st.caption(f"Models (fallback order): {' → '.join(f'`{m}`' for m in config.MODELS)} · ≤ {config.RPM:g} calls/min per model")

csv_text = SAMPLE if use_sample or upload is None else upload.getvalue().decode("utf-8-sig")
csv_name = "financials-sample.csv" if use_sample or upload is None else upload.name

# Preview: deterministic, free, instant.
try:
    rows, ignored = load_csv(csv_text)
    m = summarise(rows)
    st.subheader(f"Your numbers (FY{m['year']}): preview")
    c = st.columns(5)
    c[0].metric("Revenue", money(m["revenue"]))
    c[1].metric("Growth", p(m["revenue_growth_pct"]) if m["revenue_growth_pct"] is not None else "n/a")
    c[2].metric("Gross margin", p(m["gross_margin_pct"]))
    c[3].metric("Net margin", p(m["net_margin_pct"]))
    c[4].metric("Opex ratio", p(m["opex_ratio_pct"]))
    if ignored:
        st.info(f"Ignored non-numeric column(s): {', '.join(ignored)}. Text in the CSV never reaches the model.")
    csv_ok = True
except BadCSV as e:
    st.error(f"CSV problem: {e}")
    csv_ok = False

names = [x.strip() for x in competitors.splitlines() if x.strip()]
go = st.button("Generate report", type="primary", disabled=not (csv_ok and company.strip() and names))

if go:
    from peerbench.graph import stream_run

    final = None
    with st.status("Running PeerBench…", expanded=True) as status:
        try:
            for node, update in stream_run(company.strip(), csv_text, names, max_rev, csv_name):
                if node == "__final__":
                    final = update
                    continue
                label = STEPS.get(node, node)
                if node == "resolve_peers":
                    found = ", ".join(f"{k} → {v['ticker']}" for k, v in update.get("resolved", {}).items()) or "none"
                    label += f": {found}" + (f" · unresolved: {', '.join(update['unresolved'])}" if update.get("unresolved") else "")
                elif node == "write_report":
                    label += f" (revision {update.get('revision')})"
                elif node == "check_numbers":
                    v = update.get("violations") or []
                    label += ": all traced ✅" if not v else f": {len(v)} untraceable ⚠️ {', '.join(v[:5])}"
                elif node == "critique":
                    label += f": score {update.get('score')}/10"
                elif node in ("research_context", "research_critique"):
                    label += f": {len(update.get('snippets', []))} sources"
                st.write(f"✔ {label}")
            ok = final and not final.get("violations") and final.get("peer_metrics")
            status.update(label="Report ready" if ok else "Report ready: needs review",
                          state="complete" if ok else "error", expanded=False)
        except Exception as e:  # rate limit, network, etc.
            status.update(label="Run failed", state="error")
            st.error(f"{type(e).__name__}: {str(e)[:400]}")

    if final:
        st.session_state["final"] = final

final = st.session_state.get("final")
if final:
    if final.get("violations"):
        st.warning("Some numbers could not be traced to the data. See the banner in the report.")
    if not final.get("peer_metrics"):
        st.warning("No competitor could be resolved to a listed company, so there is nothing to benchmark against.")

# Reports are read from disk, so a finished run survives a dropped browser session (e.g. phone screen lock).
reports = sorted(config.REPORTS.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
if reports:
    st.divider()
    names_ = [f.name for f in reports[:20]]
    default = names_.index(Path(final["report_path"]).name) if final and Path(final["report_path"]).name in names_ else 0
    pick = reports[st.selectbox("Report", range(len(names_)), index=default, format_func=lambda i: names_[i])]
    text = pick.read_text(encoding="utf-8")
    run_id = pick.stem.rsplit("-", 1)[-1]
    tab_report, tab_trace = st.tabs(["Report", "Run trace"])
    with tab_report:
        st.download_button("Download report (.md)", text, pick.name, "text/markdown")
        st.markdown(text)
    with tab_trace:
        trace = next((t for t in config.RUNS.glob(f"{run_id}*.jsonl")), None)
        st.caption(f"Saved to `{pick}`")
        if trace:
            st.dataframe([json.loads(l) for l in trace.read_text(encoding="utf-8").splitlines()], width="stretch")
