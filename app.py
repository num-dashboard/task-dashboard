import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# =========================
# CONFIG
# =========================
SPREADSHEET_NAME = "Team Task Tracker"
TASKS_SHEET = "Tasks"
SERVICE_ACCOUNT_FILE = "service_account.json"

# =========================
# AUTH
# =========================
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
client = gspread.authorize(creds)

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=30)
def load_tasks():
    ws = client.open(SPREADSHEET_NAME).worksheet(TASKS_SHEET)
    df = pd.DataFrame(ws.get_all_records())

    # Clean column names
    df.columns = df.columns.astype(str).str.strip()

    # Ensure columns exist
    for col in ["Owner", "Project", "Status", "Deadline"]:
        if col not in df.columns:
            df[col] = ""

    return df


def status_rank(s):
    if pd.isna(s):
        return 99
    s = str(s).strip().lower()
    if s == "blocked":
        return 0
    if s == "in progress":
        return 1
    if s == "not started":
        return 2
    if s == "done":
        return 3
    return 50


# =========================
# UI
# =========================
st.set_page_config(page_title="Task Dashboard", layout="wide")
st.title("📊 Task Dashboard")

df = load_tasks()

# =========================
# KPI METRICS
# =========================
status_lower = df["Status"].astype(str).str.strip().str.lower()

total_tasks = len(df)
blocked_count = (status_lower == "blocked").sum()
in_progress_count = (status_lower == "in progress").sum()
done_count = (status_lower == "done").sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Tasks", total_tasks)
c2.metric("Blocked", int(blocked_count))
c3.metric("In Progress", int(in_progress_count))
c4.metric("Done", int(done_count))

st.divider()

# =========================
# FILTERS
# =========================
owners = sorted([o for o in df["Owner"].dropna().unique() if str(o).strip()])
projects = sorted([p for p in df["Project"].dropna().unique() if str(p).strip()])

col1, col2 = st.columns(2)

with col1:
    selected_owner = st.selectbox("Select Owner", ["All"] + owners)

with col2:
    selected_project = st.selectbox("Select Project", ["All"] + projects)

filtered = df.copy()

if selected_owner != "All":
    filtered = filtered[filtered["Owner"] == selected_owner]

if selected_project != "All":
    filtered = filtered[filtered["Project"] == selected_project]

# =========================
# SORTING (Blocked → In Progress → Not Started → Done)
# =========================
view = filtered.copy()
view["__rank"] = view["Status"].apply(status_rank)

view = view.sort_values(by=["__rank", "Deadline"], ascending=[True, True])
view = view.drop(columns="__rank")

# =========================
# TABLE
# =========================
display_cols = [
    "Task ID",
    "Task",
    "Project",
    "Owner",
    "Status",
    "StartDate",
    "Deadline",
    "Latest Update",
    "Blockers",
    "Project Team",
]

display_cols = [c for c in display_cols if c in view.columns]

st.subheader("Tasks")
st.dataframe(
    view[display_cols],
    use_container_width=True,
    hide_index=True,
)
