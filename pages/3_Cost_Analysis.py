import streamlit as st
import pandas as pd
import plotly.express as px

from helpers import load_all_data, fmt_usd, fmt_pct

st.set_page_config(page_title="Cost Analysis — WrenchLane", layout="wide")
st.header("Cost Analysis")

data = load_all_data()
cost = data["cost_analysis"]
diag = data["diagnostics"]
chats = data["diagnostics_chat"]

if not cost:
    st.info("No cost data available yet.")
    st.stop()

d = cost["diagnostics"]
c = cost["chats"]
combined = cost["combined"]

# ---------------------------------------------------------------------------
# Summary Cards
# ---------------------------------------------------------------------------
st.subheader("Diagnostics Cost")
st.caption("AI token costs for the initial diagnostic analysis")
d1, d2, d3, d4, d5 = st.columns(5)
d1.metric(
    "Total", fmt_usd(d["total_cost"]), help="Sum of all diagnostic analysis costs"
)
d2.metric("Average", fmt_usd(d["avg_cost"]), help="Mean cost per diagnostic")
d3.metric(
    "Median",
    fmt_usd(d["median_cost"]),
    help="Middle value — half of diagnostics cost less than this",
)
d4.metric(
    "P90",
    fmt_usd(d["p90_cost"]),
    help="90th percentile — 90% of diagnostics cost less than this",
)
d5.metric("Count", f"{d['count']:,}")

st.subheader("Chat Cost")
st.caption("AI token costs for follow-up chat conversations after a diagnostic")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total", fmt_usd(c["total_cost"]), help="Sum of all chat costs")
c2.metric("Average", fmt_usd(c["avg_cost"]), help="Mean cost per chat session")
c3.metric(
    "Median",
    fmt_usd(c["median_cost"]),
    help="Middle value — half of chats cost less than this",
)
c4.metric(
    "P90",
    fmt_usd(c["p90_cost"]),
    help="90th percentile — 90% of chats cost less than this",
)
c5.metric(
    "Avg Msgs/Chat",
    f"{c['avg_messages_per_chat']}",
    help="Average number of AI exchanges per chat",
)

st.divider()

# ---------------------------------------------------------------------------
# Combined Metrics
# ---------------------------------------------------------------------------
st.subheader("Combined")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Platform Cost", fmt_usd(combined["total_cost"]))
m2.metric("Blended Cost/Diagnostic", fmt_usd(combined["blended_cost_per_diagnostic"]))
m3.metric(
    "Chat Adoption",
    fmt_pct(combined["chat_adoption_rate"] * 100),
    help=f"{combined['diagnostics_with_chat']} diagnostics had a chat",
)

split = combined["cost_split"]
m4.write("**Cost Split**")
m4.write(f"Diagnostics: {split['diagnostics_pct']:.1f}%")
m4.write(f"Chats: {split['chats_pct']:.1f}%")

st.divider()

# ---------------------------------------------------------------------------
# By Model Breakdown
# ---------------------------------------------------------------------------
st.subheader("Cost by AI Model")

# Diagnostics by model
diag_models = d.get("by_model", {})
if diag_models:
    model_rows = []
    for model, m in diag_models.items():
        model_rows.append(
            {
                "Model": model,
                "Type": "Diagnostic",
                "Count": m["count"],
                "Total Cost": fmt_usd(m["cost"]),
                "Avg Cost": fmt_usd(m["avg_cost"]),
                "Input Tokens": f"{m['input_tokens']:,}",
                "Output Tokens": f"{m['output_tokens']:,}",
            }
        )

    # Chat by model
    chat_models = c.get("by_model", {})
    for model, m in chat_models.items():
        model_rows.append(
            {
                "Model": model,
                "Type": "Chat",
                "Count": m.get("messages", 0),
                "Total Cost": fmt_usd(m["cost"]),
                "Avg Cost": "—",
                "Input Tokens": "—",
                "Output Tokens": "—",
            }
        )

    st.dataframe(pd.DataFrame(model_rows), use_container_width=True, hide_index=True)

    # Bar chart: cost by model
    chart_data = []
    for model, m in diag_models.items():
        chart_data.append({"Model": model, "USD": m["cost"], "Type": "Diagnostic"})
    for model, m in chat_models.items():
        chart_data.append({"Model": model, "USD": m["cost"], "Type": "Chat"})

    if chart_data:
        fig = px.bar(
            pd.DataFrame(chart_data),
            x="Model",
            y="USD",
            color="Type",
            title="Cost by Model",
            barmode="stack",
        )
        fig.update_layout(height=350, xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Cost Distribution
# ---------------------------------------------------------------------------
st.subheader("Cost Distribution")

col1, col2 = st.columns(2)

with col1:
    if not diag.empty and "diag_cost" in diag.columns:
        fig2 = px.histogram(
            diag,
            x="diag_cost",
            nbins=50,
            title="Diagnostic Cost Distribution",
            labels={"diag_cost": "Cost (USD)"},
        )
        fig2.update_traces(hovertemplate="Cost (USD)=%{x}<br>Count=%{y}<extra></extra>")
        fig2.update_layout(height=350, yaxis_title="Count")
        st.plotly_chart(fig2, use_container_width=True)

with col2:
    if not chats.empty and "chat_cost" in chats.columns:
        fig3 = px.histogram(
            chats,
            x="chat_cost",
            nbins=50,
            title="Chat Cost Distribution",
            labels={"chat_cost": "Cost (USD)"},
        )
        fig3.update_traces(hovertemplate="Cost (USD)=%{x}<br>Count=%{y}<extra></extra>")
        fig3.update_layout(height=350, yaxis_title="Count")
        st.plotly_chart(fig3, use_container_width=True)

# ---------------------------------------------------------------------------
# Pricing Reference
# ---------------------------------------------------------------------------
with st.expander("Pricing Table (USD per 1M tokens)"):
    pricing = cost.get("pricing_table", {})
    rows = []
    for model, p in sorted(pricing.items()):
        rows.append(
            {
                "Model": model,
                "Input": f"${p['input']:.2f}",
                "Output": f"${p['output']:.2f}",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True)
