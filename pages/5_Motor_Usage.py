import streamlit as st
import pandas as pd
import plotly.express as px

from helpers import load_all_data

st.set_page_config(page_title="Motor Usage — WrenchLane", layout="wide")
st.header("Motor API Usage")
st.caption("MSA Section 4 compliance — $1/VIN/year/database")

data = load_all_data()
motor = data["motor_usage"]

if motor.empty:
    st.info("No Motor API usage data yet.")
    st.stop()

# ---------------------------------------------------------------------------
# Summary Metrics
# ---------------------------------------------------------------------------
m1, m2, m3 = st.columns(3)
m1.metric("Total Accesses", int(motor["total_accesses"].sum()))
m2.metric("Unique Vehicles (all time)", int(motor["unique_vehicles"].sum()))
m3.metric("Unique Users (all time)", int(motor["unique_users"].sum()))

st.divider()

# ---------------------------------------------------------------------------
# Per-Database Table
# ---------------------------------------------------------------------------
st.subheader("By Database")

db_summary = (
    motor.groupby("database")
    .agg(
        total_accesses=("total_accesses", "sum"),
        unique_vehicles=("unique_vehicles", "sum"),
        unique_users=("unique_users", "sum"),
        months=("month", "nunique"),
    )
    .reset_index()
    .sort_values("total_accesses", ascending=False)
)
db_summary = db_summary.rename(
    columns={
        "database": "Database",
        "total_accesses": "Total Accesses",
        "unique_vehicles": "Unique Vehicles",
        "unique_users": "Unique Users",
        "months": "Months",
    }
)
st.dataframe(db_summary, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Monthly Trend
# ---------------------------------------------------------------------------
st.subheader("Monthly Trend")

motor_sorted = motor.sort_values("month")
fig = px.bar(
    motor_sorted,
    x="month",
    y="total_accesses",
    color="database",
    title="Accesses per Month by Database",
    labels={"month": "Month", "total_accesses": "Accesses", "database": "Database"},
    barmode="group",
)
fig.update_layout(height=400, xaxis_title="")
st.plotly_chart(fig, use_container_width=True)

# Vehicles trend
fig2 = px.bar(
    motor_sorted,
    x="month",
    y="unique_vehicles",
    color="database",
    title="Unique Vehicles per Month by Database",
    labels={"month": "Month", "unique_vehicles": "Vehicles", "database": "Database"},
    barmode="group",
)
fig2.update_layout(height=400, xaxis_title="")
st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------------------
# Raw Data
# ---------------------------------------------------------------------------
with st.expander("Raw Data"):
    st.dataframe(motor_sorted, use_container_width=True, hide_index=True)
