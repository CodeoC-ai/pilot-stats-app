"""Archive page — v1 data (read-only, pre-March 2026)."""

import gzip
import io
import json

import streamlit as st
import pandas as pd

from helpers import get_s3_client, DATA_BUCKET

st.set_page_config(page_title="Archive (v1) — WrenchLane", layout="wide")
st.header("Archive — v1 Data")
st.info(
    "This page shows archived data from the v1 system (before March 2026). "
    "This data is read-only and will not update."
)


@st.cache_data(ttl=3600)
def load_v1_data():
    """Load v1 archive data from S3 v1/ prefix."""
    s3 = get_s3_client()
    result = {}
    for key, name in [
        ("v1/user_stats.json.gz", "user_stats"),
        ("v1/user_conversations.json.gz", "user_conversations"),
    ]:
        try:
            obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
            with gzip.GzipFile(fileobj=io.BytesIO(obj["Body"].read())) as gz:
                result[name] = pd.DataFrame(json.loads(gz.read().decode()))
        except Exception:
            result[name] = pd.DataFrame()
    return result


v1 = load_v1_data()
user_stats = v1["user_stats"]
conversations = v1["user_conversations"]

if user_stats.empty and conversations.empty:
    st.warning(
        "No v1 archive data found. The v1/ prefix in S3 may not have been created yet."
    )
    st.stop()

# Parse dates
if not user_stats.empty and "last_login" in user_stats.columns:
    user_stats["last_login"] = pd.to_datetime(
        user_stats["last_login"], format="mixed", utc=True, errors="coerce"
    )
if not conversations.empty:
    for col in ["created_at", "updated_at"]:
        if col in conversations.columns:
            conversations[col] = pd.to_datetime(
                conversations[col], format="mixed", utc=True, errors="coerce"
            )

# Merge
if not conversations.empty and not user_stats.empty:
    conversations = conversations.merge(
        user_stats[
            ["user_id", "email", "user_role", "workshop_id", "company_name"]
        ].drop_duplicates(),
        on="user_id",
        how="left",
    )

# ---------------------------------------------------------------------------
# Global Stats
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("Global Stats (v1)")
    if not user_stats.empty:
        g1, g2, g3 = st.columns(3)
        g1.metric("Users", len(user_stats))
        g2.metric("Workshops", user_stats["workshop_id"].nunique())
        total_mechanics = (
            len(user_stats[user_stats["user_role"] == "mechanic"])
            if "user_role" in user_stats.columns
            else "?"
        )
        g3.metric("Mechanics", total_mechanics)

    if not conversations.empty:
        g4, g5, g6 = st.columns(3)
        g4.metric("Total Chats", len(conversations))
        verified = (
            len(conversations[conversations.get("open_search", pd.Series()) == False])
            if "open_search" in conversations.columns
            else "?"
        )
        g5.metric("Verified Answers", verified)
        if "tot_cost" in conversations.columns:
            g6.metric(
                "Avg Cost/Chat",
                (
                    f"${conversations['tot_cost'].mean():.4f}"
                    if conversations["tot_cost"].notna().any()
                    else "N/A"
                ),
            )

with col2:
    st.subheader("Browse by Company (v1)")
    if not user_stats.empty:
        companies = sorted(user_stats["company_name"].dropna().unique().tolist())
        selected = st.selectbox("Company", companies, key="v1_company")

        if selected:
            ws_users = user_stats[user_stats["company_name"] == selected]
            st.write(f"**Workshop ID:** {ws_users['workshop_id'].iloc[0]}")

            user_opts = ws_users.apply(
                lambda r: f"{r['user_id']} ({r.get('user_role', '?')})", axis=1
            ).tolist()
            user_ids = ws_users["user_id"].tolist()
            selected_user_opt = st.selectbox("User", user_opts, key="v1_user")

            if selected_user_opt:
                idx = user_opts.index(selected_user_opt)
                uid = user_ids[idx]
                u = ws_users[ws_users["user_id"] == uid].iloc[0]

                st.write(f"**Email:** {u.get('email', 'N/A')}")
                st.write(f"**Role:** {u.get('user_role', 'N/A')}")

                # User conversations
                if not conversations.empty:
                    user_convs = conversations[
                        conversations["user_id"] == uid
                    ].sort_values("updated_at", ascending=False)

                    if not user_convs.empty:
                        chat_opts = user_convs.apply(
                            lambda r: f"{r['updated_at'].strftime('%Y-%m-%d %H:%M') if pd.notna(r.get('updated_at')) else '?'} — {r.get('title', '?')}",
                            axis=1,
                        ).tolist()
                        selected_chat = st.selectbox("Chat", chat_opts, key="v1_chat")
                        if selected_chat:
                            c_idx = chat_opts.index(selected_chat)
                            chat = user_convs.iloc[c_idx]

                            st.write(f"**Title:** {chat.get('title')}")
                            st.write(
                                f"**Verified:** {not chat.get('open_search', True)}"
                            )
                            st.write(f"**Cost:** ${chat.get('tot_cost', 0)}")
                            st.write(f"**REGNO:** {chat.get('regno')}")

                            messages = chat.get("messages") or []
                            if messages:
                                with st.expander("Messages", expanded=False):
                                    for msg in messages:
                                        role = msg.get("role", "")
                                        content = msg.get("content", "")
                                        if role != "system":
                                            label = (
                                                "User"
                                                if role == "user"
                                                else "Assistant"
                                            )
                                            st.markdown(f"**{label}:** {content}")
                    else:
                        st.write("No chats for this user.")
