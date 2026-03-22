import streamlit as st
import pandas as pd

from helpers import load_all_data, fmt_usd

st.set_page_config(page_title="Customers — WrenchLane", layout="wide")
st.header("Customers")

data = load_all_data()
users = data["user_stats"]
diag = data["diagnostics"]
chats = data["diagnostics_chat"]

if users.empty:
    st.info("No user data available yet.")
    st.stop()

# Enrich users with diagnostic counts
user_diag_counts = (
    diag.groupby("user_id").size().reset_index(name="diag_count")
    if not diag.empty
    else pd.DataFrame(columns=["user_id", "diag_count"])
)
users_enriched = users.merge(user_diag_counts, on="user_id", how="left")
users_enriched["diag_count"] = users_enriched["diag_count"].fillna(0).astype(int)

# ---------------------------------------------------------------------------
# Workshop Selector
# ---------------------------------------------------------------------------
companies = sorted(users_enriched["company_name"].dropna().unique().tolist())
selected_company = st.selectbox(
    "Select a Workshop", companies, index=None, placeholder="Choose a workshop..."
)

if not selected_company:
    st.info("Select a workshop above to see details.")
    st.stop()

ws_users = users_enriched[users_enriched["company_name"] == selected_company]

# Workshop Card
st.subheader(selected_company)
ws_user_ids = set(ws_users["user_id"])
ws_diags = diag[diag["user_id"].isin(ws_user_ids)] if not diag.empty else pd.DataFrame()
ws_chats = (
    chats[chats["user_id"].isin(ws_user_ids)] if not chats.empty else pd.DataFrame()
)
total_cost = ws_diags["diag_cost"].sum() if not ws_diags.empty else 0
total_cost += ws_chats["chat_cost"].sum() if not ws_chats.empty else 0

wc1, wc2, wc3, wc4, wc5 = st.columns(5)
wc1.metric("Users", len(ws_users))
wc2.metric("Diagnostics", len(ws_diags))
wc3.metric("Chats", len(ws_chats))
wc4.metric("Total Cost", fmt_usd(total_cost))
credits = ws_users["credits_remaining"].iloc[0]
wc5.metric("Credits", int(credits) if pd.notna(credits) else "N/A")

ws_id = ws_users["workshop_id"].iloc[0]
plan = ws_users["plan_type"].iloc[0] or "N/A"
last_active_ws = (
    ws_users["last_active"].dropna().max()
    if "last_active" in ws_users.columns
    else None
)
info_parts = [f"**Plan:** {plan}", f"**Workshop ID:** `{ws_id}`"]
if pd.notna(last_active_ws):
    info_parts.append(f"**Last active:** {last_active_ws.strftime('%Y-%m-%d %H:%M')}")
st.caption(" | ".join(info_parts))

st.divider()

# ---------------------------------------------------------------------------
# Users Table
# ---------------------------------------------------------------------------
st.subheader("Users")

user_table = ws_users[
    ["email", "user_role", "last_active", "login_count", "diag_count"]
].copy()
if "last_active" in user_table.columns:
    user_table["last_active"] = user_table["last_active"].apply(
        lambda x: x.strftime("%Y-%m-%d %H:%M") if pd.notna(x) else "Never"
    )
user_table = user_table.sort_values("diag_count", ascending=False)
user_table = user_table.rename(
    columns={
        "email": "Email",
        "user_role": "Role",
        "last_active": "Last Active",
        "login_count": "Logins",
        "diag_count": "Diagnostics",
    }
)
st.dataframe(user_table, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# User Drill-Down
# ---------------------------------------------------------------------------
st.subheader("User Detail")

user_options = ws_users.apply(
    lambda r: f"{r['email'] or r['user_id']} ({r['user_role']})", axis=1
).tolist()
user_ids = ws_users["user_id"].tolist()

selected_user_label = st.selectbox("Select a user", user_options)
if not selected_user_label:
    st.stop()

selected_idx = user_options.index(selected_user_label)
selected_uid = user_ids[selected_idx]
user_row = ws_users[ws_users["user_id"] == selected_uid].iloc[0]

uc1, uc2, uc3 = st.columns(3)
uc1.write(f"**Email:** {user_row.get('email', 'N/A')}")
uc2.write(f"**Role:** {user_row.get('user_role', 'N/A')}")
la = user_row.get("last_active")
uc3.write(
    f"**Last Active:** {la.strftime('%Y-%m-%d %H:%M') if pd.notna(la) else 'Never'}"
)

# User's diagnostics
user_diags = (
    ws_diags[ws_diags["user_id"] == selected_uid]
    if not ws_diags.empty
    else pd.DataFrame()
)
if not user_diags.empty:
    with st.expander(f"Diagnostics ({len(user_diags)})", expanded=True):
        diag_table = user_diags[
            [
                "created_at",
                "status",
                "car_make",
                "car_model",
                "dtcs",
                "diag_cost",
                "has_chat",
            ]
        ].copy()
        diag_table["created_at"] = diag_table["created_at"].apply(
            lambda x: x.strftime("%Y-%m-%d %H:%M") if pd.notna(x) else "?"
        )
        diag_table["diag_cost"] = diag_table["diag_cost"].apply(fmt_usd)
        diag_table["dtcs"] = diag_table["dtcs"].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else ""
        )
        diag_table = diag_table.sort_values("created_at", ascending=False)
        diag_table = diag_table.rename(
            columns={
                "created_at": "Created",
                "status": "Status",
                "car_make": "Make",
                "car_model": "Model",
                "dtcs": "DTCs",
                "diag_cost": "Cost",
                "has_chat": "Chat",
            }
        )
        st.dataframe(diag_table, use_container_width=True, hide_index=True)

        # Chat viewer for selected diagnostic
        diag_with_chat = user_diags[user_diags["has_chat"] == True]
        if not diag_with_chat.empty and not chats.empty:
            chat_labels = []
            chat_diag_ids = []
            for _, d_row in diag_with_chat.iterrows():
                ts = (
                    d_row["created_at"].strftime("%Y-%m-%d %H:%M")
                    if pd.notna(d_row.get("created_at"))
                    else "?"
                )
                chat_labels.append(f"{ts} — {d_row['diagnostics_id'][:8]}")
                chat_diag_ids.append(d_row["diagnostics_id"])

            selected_chat_label = st.selectbox("View chat for diagnostic", chat_labels)
            if selected_chat_label:
                chat_idx = chat_labels.index(selected_chat_label)
                chat_diag_id = chat_diag_ids[chat_idx]
                chat_row = chats[chats["diagnostics_id"] == chat_diag_id]
                if not chat_row.empty:
                    chat = chat_row.iloc[0]
                    st.caption(
                        f"Chat: {chat['message_count']} messages, cost: {fmt_usd(chat['chat_cost'])}"
                    )
                    messages = chat.get("messages") or []
                    for msg in messages:
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "user":
                            st.markdown(f"**User:** {content}")
                        elif role == "assistant":
                            st.markdown(f"**Assistant:** {content}")
else:
    st.info("No diagnostics for this user.")
