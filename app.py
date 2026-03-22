import streamlit as st

st.set_page_config(
    page_title="WrenchLane Dashboard",
    page_icon="🔧",
    layout="wide",
)

st.title("WrenchLane Dashboard")
st.markdown(
    "Internal analytics for the WrenchLane team. Data refreshes daily at 02:15 UTC."
)

st.markdown(
    """
| Page | What it shows |
|---|---|
| **Overview** | High-level KPIs — users, workshops, diagnostics volume, active users, AI cost, and trends over time |
| **Diagnostics** | Explore every diagnostic: filter by date/status/workshop, drill into the AI response (possible causes, probabilities, suggested tests), see user actions and follow-up chats |
| **Cost Analysis** | AI token costs broken down by model, with averages, medians, P90, distribution histograms, and diagnostics vs chat cost split |
| **Customers** | CRM-style view — pick a workshop to see its users, activity, diagnostics, and read individual chat conversations |
| **Motor Usage** | Motor API usage tracking for MSA compliance reporting ($1/VIN/year/database) |
| **Archive** | Read-only snapshot of the old v1 system data (before March 2026) |
"""
)
