import streamlit as st
import pandas as pd
import plotly.express as px

from helpers import load_all_data, fmt_usd

st.set_page_config(page_title="Diagnostics — WrenchLane", layout="wide")
st.header("Diagnostics Explorer")

data = load_all_data()
users = data["user_stats"]
diag = data["diagnostics"]
chats = data["diagnostics_chat"]

if diag.empty:
    st.info("No diagnostics data available yet.")
    st.stop()

# Merge user info into diagnostics for display
diag_display = diag.merge(
    users[["user_id", "email", "company_name"]].drop_duplicates(),
    on="user_id",
    how="left",
)

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    min_date = diag_display["created_at"].min()
    max_date = diag_display["created_at"].max()
    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.date_input(
            "Date range",
            value=(min_date.date(), max_date.date()),
            min_value=min_date.date(),
            max_value=max_date.date(),
        )
    else:
        date_range = None

with col_f2:
    statuses = ["All"] + sorted(diag_display["status"].dropna().unique().tolist())
    selected_status = st.selectbox("Status", statuses)

with col_f3:
    companies = ["All"] + sorted(
        diag_display["company_name"].dropna().unique().tolist()
    )
    selected_company = st.selectbox("Workshop", companies)

# Apply filters
filtered = diag_display.copy()
if date_range and len(date_range) == 2:
    start = pd.Timestamp(date_range[0], tz="UTC")
    end = pd.Timestamp(date_range[1], tz="UTC") + pd.Timedelta(days=1)
    filtered = filtered[
        (filtered["created_at"] >= start) & (filtered["created_at"] < end)
    ]
if selected_status != "All":
    filtered = filtered[filtered["status"] == selected_status]
if selected_company != "All":
    filtered = filtered[filtered["company_name"] == selected_company]

st.caption(f"{len(filtered)} diagnostics matching filters")

# ---------------------------------------------------------------------------
# Diagnostics Table
# ---------------------------------------------------------------------------
table_cols = [
    "created_at",
    "email",
    "company_name",
    "status",
    "car_make",
    "car_model",
    "dtcs",
    "diag_cost",
    "has_chat",
]
display_df = filtered[[c for c in table_cols if c in filtered.columns]].copy()
if "created_at" in display_df.columns:
    display_df["created_at"] = display_df["created_at"].dt.strftime("%Y-%m-%d %H:%M")
if "diag_cost" in display_df.columns:
    display_df["diag_cost"] = display_df["diag_cost"].apply(fmt_usd)
if "dtcs" in display_df.columns:
    display_df["dtcs"] = display_df["dtcs"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else ""
    )
if "email" in display_df.columns:
    display_df["email"] = display_df["email"].fillna("—")
if "company_name" in display_df.columns:
    display_df["company_name"] = display_df["company_name"].fillna("—")

col_rename = {
    "created_at": "Created",
    "email": "Email",
    "company_name": "Workshop",
    "status": "Status",
    "car_make": "Make",
    "car_model": "Model",
    "dtcs": "DTCs",
    "diag_cost": "Cost",
    "has_chat": "Chat",
}
display_df = display_df.rename(columns=col_rename)

st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)

# ---------------------------------------------------------------------------
# Diagnostic Drill-Down
# ---------------------------------------------------------------------------
st.subheader("Diagnostic Detail")
diag_ids = filtered["diagnostics_id"].tolist()
if diag_ids:
    # Build selector labels
    labels = []
    for _, row in filtered.iterrows():
        ts = (
            row["created_at"].strftime("%Y-%m-%d %H:%M")
            if pd.notna(row.get("created_at"))
            else "?"
        )
        email = row.get("email")
        email_str = email if pd.notna(email) else "unknown"
        labels.append(f"{ts} — {email_str} — {row['diagnostics_id']}")
    selected_label = st.selectbox("Select a diagnostic", labels)
    if selected_label:
        idx = labels.index(selected_label)
        row = filtered.iloc[idx]

        c1, c2, c3, c4 = st.columns(4)
        c1.write(f"**Status:** {row['status']}")
        c2.write(f"**Cost:** {fmt_usd(row['diag_cost'])}")
        c3.write(f"**Model:** {row.get('ai_model', 'N/A')}")
        c4.write(f"**Causes:** {row.get('num_causes', 0)}")

        # Parent / children relationships
        parent_id = row.get("parent_diagnostics_id")
        diag_id = row["diagnostics_id"]

        if pd.notna(parent_id) and parent_id:
            parent_row = filtered[filtered["diagnostics_id"] == parent_id]
            if parent_row.empty:
                # Parent might be outside current filter — check full dataset
                parent_row = diag_display[diag_display["diagnostics_id"] == parent_id]
            with st.expander("Refinement — parent diagnostic", expanded=False):
                if not parent_row.empty:
                    p = parent_row.iloc[0]
                    p_ts = (
                        p["created_at"].strftime("%Y-%m-%d %H:%M")
                        if pd.notna(p.get("created_at"))
                        else "?"
                    )
                    st.write(f"**Parent:** `{parent_id}` — {p_ts}")
                    st.write(
                        f"**Status:** {p.get('status')} | **Causes:** {p.get('num_causes', '?')} | **Cost:** {fmt_usd(p.get('diag_cost', 0))}"
                    )
                    parent_causes = p.get("possible_causes")
                    if isinstance(parent_causes, list) and parent_causes:
                        cause_names = [c.get("name", "?") for c in parent_causes]
                        st.write("**Parent causes:** " + ", ".join(cause_names))
                else:
                    st.write(f"Parent: `{parent_id}` (not found in current data)")

        # Check if this diagnostic has children (refinements)
        children = diag_display[diag_display["parent_diagnostics_id"] == diag_id]
        if not children.empty:
            with st.expander(f"Has {len(children)} refinement(s)", expanded=False):
                for _, child in children.iterrows():
                    c_ts = (
                        child["created_at"].strftime("%Y-%m-%d %H:%M")
                        if pd.notna(child.get("created_at"))
                        else "?"
                    )
                    st.write(
                        f"- `{child['diagnostics_id']}` — {c_ts} — "
                        f"status: {child.get('status')} — causes: {child.get('num_causes', '?')}"
                    )

        with st.expander("Car Info & Input", expanded=True):
            cc1, cc2 = st.columns(2)
            cc1.write(f"**Make:** {row.get('car_make', 'N/A')}")
            cc1.write(f"**Model:** {row.get('car_model', 'N/A')}")
            cc1.write(f"**Year:** {row.get('car_year', 'N/A')}")
            cc2.write(
                f"**DTCs:** {', '.join(row['dtcs']) if isinstance(row.get('dtcs'), list) else 'None'}"
            )
            cc2.write(
                f"**Symptoms:** {', '.join(row['symptoms']) if isinstance(row.get('symptoms'), list) else 'None'}"
            )
            cc2.write(f"**Description:** {row.get('description') or 'N/A'}")

        # Possible causes (the AI response)
        causes = row.get("possible_causes")
        if isinstance(causes, list) and causes:
            with st.expander(f"Possible Causes ({len(causes)})", expanded=True):
                for i, cause in enumerate(causes):
                    prob = cause.get("probability", 0)
                    severity = cause.get("severity", "?")
                    prob_pct = (
                        f"{prob * 100:.0f}%"
                        if isinstance(prob, (int, float))
                        else str(prob)
                    )
                    cause_id = cause.get("id", "")
                    st.markdown(
                        f"**{i+1}. {cause.get('name', 'Unknown')}** — "
                        f"probability: {prob_pct}, severity: {severity}"
                    )
                    st.caption(f"ID: `{cause_id}`")
                    st.write(cause.get("description", ""))
                    tests = cause.get("suggested_tests")
                    if tests:
                        st.caption("Suggested tests: " + " | ".join(tests))
                    st.divider()

        # User actions
        ua = row.get("user_actions")
        if isinstance(ua, dict) and ua:
            with st.expander("User Actions"):
                for key, val in ua.items():
                    label = key.replace("_", " ").title()
                    if isinstance(val, list):
                        st.write(f"**{label}:** {', '.join(str(v) for v in val)}")
                    elif isinstance(val, bool):
                        st.write(f"**{label}:** {'Yes' if val else 'No'}")
                    else:
                        st.write(f"**{label}:** {val}")
        else:
            with st.expander("User Actions"):
                st.caption("No user interactions recorded for this diagnostic.")

        with st.expander("Timestamps"):
            for ts_col in [
                "created_at",
                "updated_at",
                "analyzed_at",
                "completed_at",
            ]:
                val = row.get(ts_col)
                display_val = (
                    val.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(val) else "—"
                )
                st.write(f"**{ts_col}:** {display_val}")

        # Show chat if exists
        if row.get("has_chat") and not chats.empty:
            chat_row = chats[chats["diagnostics_id"] == row["diagnostics_id"]]
            if not chat_row.empty:
                chat = chat_row.iloc[0]
                with st.expander(
                    f"Chat ({chat['message_count']} messages, {fmt_usd(chat['chat_cost'])})"
                ):
                    messages = chat.get("messages") or []
                    for msg in messages:
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "user":
                            st.markdown(f"**User:** {content}")
                        elif role == "assistant":
                            st.markdown(f"**Assistant:** {content}")

st.divider()

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
st.subheader("Patterns")
p1, p2 = st.columns(2)

with p1:
    # Most common DTCs
    all_dtcs = [
        dtc
        for dtcs in filtered["dtcs"].dropna()
        if isinstance(dtcs, list)
        for dtc in dtcs
    ]
    if all_dtcs:
        dtc_counts = pd.Series(all_dtcs).value_counts().head(15).reset_index()
        dtc_counts.columns = ["DTC", "Count"]
        fig = px.bar(
            dtc_counts,
            x="Count",
            y="DTC",
            orientation="h",
            title="Most Common DTCs",
        )
        fig.update_layout(yaxis=dict(autorange="reversed"), height=400)
        st.plotly_chart(fig, use_container_width=True)

with p2:
    # Most common cars
    if "car_make" in filtered.columns:
        car_counts = (
            filtered.groupby(["car_make", "car_model"])
            .size()
            .reset_index(name="Count")
            .sort_values("Count", ascending=False)
            .head(15)
        )
        car_counts["Car"] = (
            car_counts["car_make"].fillna("") + " " + car_counts["car_model"].fillna("")
        )
        fig2 = px.bar(
            car_counts,
            x="Count",
            y="Car",
            orientation="h",
            title="Most Common Cars",
        )
        fig2.update_layout(yaxis=dict(autorange="reversed"), height=400)
        st.plotly_chart(fig2, use_container_width=True)

# Completion stats
m1, m2, m3 = st.columns(3)
completed = len(filtered[filtered["status"] == "completed"])
ongoing = len(filtered[filtered["status"] == "ongoing"])
failed = len(filtered[filtered["status"] == "failed"])
total_completable = completed + ongoing
m1.metric(
    "Completion Rate",
    f"{completed / total_completable * 100:.1f}%" if total_completable else "N/A",
    help="completed / (completed + ongoing)",
)
m2.metric("Failed", failed)

# Avg time to analyze
if "analyzed_at" in filtered.columns and "created_at" in filtered.columns:
    analyzed = filtered.dropna(subset=["analyzed_at", "created_at"])
    if not analyzed.empty:
        avg_time = (
            (analyzed["analyzed_at"] - analyzed["created_at"]).dt.total_seconds().mean()
        )
        if avg_time < 120:
            m3.metric("Avg Time to Analyze", f"{avg_time:.0f}s")
        else:
            m3.metric("Avg Time to Analyze", f"{avg_time / 60:.1f}min")
