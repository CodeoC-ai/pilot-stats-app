"""Shared helpers for WrenchLane Dashboard."""

import gzip
import io
import json

import boto3
import pandas as pd
import streamlit as st

REGION = st.secrets["AWS_REGION"]
DATA_BUCKET = st.secrets["DATA_BUCKET"]


def get_s3_client():
    """Create S3 client from Streamlit secrets."""
    if "AWS_ACCESS_KEY_ID" not in st.secrets:
        st.error("AWS credentials not configured in Streamlit secrets.")
        st.stop()
    session = boto3.Session(
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=REGION,
    )
    return session.client("s3")


@st.cache_data(ttl=300)
def _load_s3_json(key: str) -> list | dict:
    """Load gzip JSON from S3."""
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=DATA_BUCKET, Key=key)
    with gzip.GzipFile(fileobj=io.BytesIO(obj["Body"].read())) as gz:
        return json.loads(gz.read().decode())


@st.cache_data(ttl=300)
def load_all_data() -> dict:
    """Load all v2 dashboard data from S3. Returns dict with DataFrames + cost dict."""
    user_stats = pd.DataFrame(_load_s3_json("latest/user_stats.json.gz"))
    diagnostics = pd.DataFrame(_load_s3_json("latest/diagnostics.json.gz"))
    diagnostics_chat = pd.DataFrame(_load_s3_json("latest/diagnostics_chat.json.gz"))
    cost_analysis = _load_s3_json("latest/cost_analysis.json.gz")
    motor_usage = pd.DataFrame(_load_s3_json("latest/motor_usage.json.gz"))

    # Parse dates
    for col in ["last_active", "last_login"]:
        if col in user_stats.columns:
            user_stats[col] = pd.to_datetime(
                user_stats[col], format="mixed", utc=True, errors="coerce"
            )

    for col in ["created_at", "updated_at", "analyzed_at", "completed_at"]:
        if col in diagnostics.columns:
            diagnostics[col] = pd.to_datetime(
                diagnostics[col], format="mixed", utc=True, errors="coerce"
            )

    for col in ["created_at", "updated_at"]:
        if col in diagnostics_chat.columns:
            diagnostics_chat[col] = pd.to_datetime(
                diagnostics_chat[col], format="mixed", utc=True, errors="coerce"
            )

    return {
        "user_stats": user_stats,
        "diagnostics": diagnostics,
        "diagnostics_chat": diagnostics_chat,
        "cost_analysis": cost_analysis,
        "motor_usage": motor_usage,
    }


def fmt_usd(val: float) -> str:
    """Format a dollar amount."""
    if val == 0:
        return "$0.00"
    if abs(val) < 0.01:
        return f"${val:.4f}"
    return f"${val:.2f}"


def fmt_pct(val: float) -> str:
    """Format a percentage."""
    return f"{val:.1f}%"
