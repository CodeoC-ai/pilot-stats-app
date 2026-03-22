import streamlit as st
import pandas as pd
import plotly.express as px

from helpers import load_all_data, fmt_usd, fmt_pct

st.set_page_config(page_title="Overview — WrenchLane", layout="wide")
st.header("Overview")

data = load_all_data()
users = data["user_stats"]
diag = data["diagnostics"]
chats = data["diagnostics_chat"]
cost = data["cost_analysis"]

if users.empty:
    st.warning("No data available yet.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI Row 1: Core counts
# ---------------------------------------------------------------------------
now = pd.Timestamp.now(tz="UTC")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Users", len(users), help="Registered users across all workshops")
k2.metric(
    "Total Workshops", users["workshop_id"].nunique(), help="Unique workshop accounts"
)
k3.metric("Total Diagnostics", len(diag), help="v2 diagnostic analyses run to date")
k4.metric(
    "Total AI Cost",
    fmt_usd(cost["combined"]["total_cost"]),
    help="Combined cost of diagnostics + chats",
)

# ---------------------------------------------------------------------------
# KPI Row 2: Activity & efficiency
# ---------------------------------------------------------------------------
active_7d = 0
active_30d = 0
if "last_active" in users.columns:
    valid = users["last_active"].dropna()
    active_7d = int((valid > now - pd.Timedelta(days=7)).sum())
    active_30d = int((valid > now - pd.Timedelta(days=30)).sum())

k5, k6, k7, k8 = st.columns(4)
k5.metric(
    "Active Users (7d)",
    active_7d,
    help="Users with last_active in the past 7 days",
)
k6.metric(
    "Active Users (30d)",
    active_30d,
    help="Users with last_active in the past 30 days",
)
k7.metric(
    "Chat Adoption",
    fmt_pct(cost["combined"]["chat_adoption_rate"] * 100),
    help="% of diagnostics where the user also opened a chat",
)
k8.metric(
    "Avg Blended Cost",
    fmt_usd(cost["combined"]["blended_cost_per_diagnostic"]),
    help="(diag cost + chat cost) / total diagnostics",
)

st.divider()

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
col_left, col_right = st.columns(2)

with col_left:
    # Diagnostics per day (last 30 days)
    if not diag.empty and "created_at" in diag.columns:
        recent = diag[diag["created_at"] > now - pd.Timedelta(days=30)].copy()
        if not recent.empty:
            recent["date"] = recent["created_at"].dt.date
            daily = recent.groupby("date").size().reset_index(name="count")
            fig = px.bar(
                daily,
                x="date",
                y="count",
                title="Diagnostics per Day (last 30 days)",
                labels={"date": "Date", "count": "Diagnostics"},
            )
            fig.update_layout(showlegend=False, height=350, xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    # Diagnostics by status
    if not diag.empty:
        status_counts = diag["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig2 = px.pie(
            status_counts,
            values="Count",
            names="Status",
            title="Diagnostics by Status",
            hole=0.4,
        )
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)

with col_right:
    # Top workshops by diagnostic count
    if not diag.empty:
        diag_with_ws = diag.merge(
            users[["user_id", "company_name"]].drop_duplicates(),
            on="user_id",
            how="left",
        )
        ws_counts = diag_with_ws["company_name"].value_counts().head(10).reset_index()
        ws_counts.columns = ["Workshop", "Diagnostics"]
        fig3 = px.bar(
            ws_counts,
            x="Diagnostics",
            y="Workshop",
            orientation="h",
            title="Top 10 Workshops by Diagnostics",
        )
        fig3.update_layout(
            yaxis=dict(autorange="reversed", title=""),
            height=350,
        )
        st.plotly_chart(fig3, use_container_width=True)

    # Users by role
    if "user_role" in users.columns:
        role_counts = users["user_role"].value_counts().reset_index()
        role_counts.columns = ["Role", "Count"]
        fig4 = px.bar(
            role_counts,
            x="Role",
            y="Count",
            title="Users by Role",
        )
        fig4.update_layout(height=350, xaxis_title="")
        st.plotly_chart(fig4, use_container_width=True)
