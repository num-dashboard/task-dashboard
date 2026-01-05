import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# ---------------------------
# Page setup
# ---------------------------
st.set_page_config(page_title="Task Dashboard", page_icon="✅", layout="wide")
st.title("✅ Task Tracking Dashboard")
st.caption("Powered by Google Sheets • Streamlit Cloud-ready")

# ---------------------------
# Secrets & config
# ---------------------------
# Streamlit Secrets must include:
# [gcp_service_account]  -> service account JSON fields as TOML keys
# [sheets]
# spreadsheet_id = "..."
# worksheet_name = "Tasks" (optional; defaults to "Tasks")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

if "gcp_service_account" not in st.secrets:
    st.error("❌ Missing `gcp_service_account` in Streamlit Secrets.")
    st.stop()

if "sheets" not in st.secrets or "spreadsheet_id" not in st.secrets["sheets"]:
    st.error("❌ Missing `sheets.spreadsheet_id` in Streamlit Secrets.")
    st.stop()

SPREADSHEET_ID = st.secrets["sheets"]["spreadsheet_id"]
WORKSHEET_NAME = st.secrets["sheets"].get("worksheet_name", "Tasks")

# ---------------------------
# Google Sheets helpers
# ---------------------------
@st.cache_resource
def get_gspread_client():
    """Create a cached gspread client using Streamlit Secrets."""
    service_account_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    return gspread.authorize(creds)

@st.cache_data(ttl=60)
def load_tasks():
    """Load tasks as a DataFrame from Google Sheets."""
    client = get_gspread_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet(WORKSHEET_NAME)
    records = ws.get_all_records()

    df = pd.DataFrame(records)

    # Normalize column names
    df.columns = [str(c).strip() for c in df.columns]

    # Clean common text columns
    for col in ["Task", "Owner", "Project", "Status", "Priority", "Notes"]:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("").str.strip()

    # Parse dates if present
    for col in ["Due Date", "Created At", "Updated At"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df

def count_status(df: pd.DataFrame, status_value: str) -> int:
    if "Status" not in df.columns:
        return 0
    return int((df["Status"].astype(str).str.strip().str.lower() == status_value.lower()).sum())

# ---------------------------
# Load data
# ---------------------------
try:
    df = load_tasks()
except gspread.exceptions.WorksheetNotFound:
    st.error(
        f"❌ Worksheet '{WORKSHEET_NAME}' not found.\n\n"
        "Check the tab name in Google Sheets and the `worksheet_name` in secrets."
    )
    st.stop()
except Exception as e:
    st.error("❌ Could not load Google Sheet. Check: secrets, spreadsheet_id, and sharing permissions.")
    st.exception(e)
    st.stop()

if df.empty:
    st.info("No tasks found in the sheet yet.")
    st.stop()

# ---------------------------
# Sidebar filters
# ---------------------------
st.sidebar.header("🔎 Filters")

owners = sorted(df["Owner"].dropna().unique().tolist()) if "Owner" in df.columns else []
projects = sorted(df["Project"].dropna().unique().tolist()) if "Project" in df.columns else []
statuses = sorted(df["Status"].dropna().unique().tolist()) if "Status" in df.columns else []

owner_filter = st.sidebar.multiselect("Owner", owners, default=owners)
project_filter = st.sidebar.multiselect("Project", projects, default=projects)
status_filter = st.sidebar.multiselect("Status", statuses, default=statuses)

filtered = df.copy()

if "Owner" in filtered.columns and owner_filter:
    filtered = filtered[filtered["Owner"].isin(owner_filter)]

if "Project" in filtered.columns and project_filter:
    filtered = filtered[filtered["Project"].isin(project_filter)]

if "Status" in filtered.columns and status_filter:
    filtered = filtered[filtered["Status"].isin(status_filter)]

# ---------------------------
# KPI cards
# ---------------------------
total_tasks = len(filtered)
blocked = count_status(filtered, "Blocked")
in_progress = count_status(filtered, "In Progress")
done = count_status(filtered, "Done")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total", total_tasks)
c2.metric("Blocked", blocked)
c3.metric("In Progress", in_progress)   # ✅ requested
c4.metric("Done", done)

st.divider()

# ---------------------------
# Tasks table
# ---------------------------
st.subheader("📋 Tasks")
st.caption(f"Showing {len(filtered)} task(s) after filters.")

preferred_order = ["Task", "Owner", "Project", "Status", "Priority", "Due Date", "Notes"]
existing = [c for c in preferred_order if c in filtered.columns]
rest = [c for c in filtered.columns if c not in existing]
display_cols = existing + rest

display_df = filtered[display_cols].copy()

if "Due Date" in display_df.columns:
    display_df = display_df.sort_values(by=["Due Date"], ascending=True, na_position="last")

st.dataframe(display_df, use_container_width=True, hide_index=True)

# ---------------------------
# Manual refresh button
# ---------------------------
st.sidebar.divider()
if st.sidebar.button("🔄 Refresh now"):
    st.cache_data.clear()
    st.rerun()

st.caption("Tip: Updates from Google Sheets may take up to ~60 seconds unless you click Refresh.")
