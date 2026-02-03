import streamlit as st
import pandas as pd
import os
import re
import hashlib
import time
import secrets
from datetime import datetime
import qrcode

# ---------------- CONFIG ----------------
APP_BASE_URL = "https://epeattendance.streamlit.app"

SESSIONS_FILE = "attendance_sessions.csv"
RECORDS_FILE = "attendance_records.csv"
TOKENS_FILE = "attendance_tokens.csv"

TOKEN_VALIDITY_SECONDS = 11

SESSION_COLUMNS = ["attendance_id", "type", "title", "status", "created_at"]
RECORD_COLUMNS = ["attendance_id", "full_name", "matric", "time", "device_id"]
TOKEN_COLUMNS = ["attendance_id", "token", "created_at"]

REP_USERNAME = "rep"
REP_PASSWORD = "epe100"

# ---------------- HELPERS ----------------
def normalize_name(name):
    return re.sub(r"\s+", " ", name.strip()).lower()

def load_csv(file, cols):
    if os.path.exists(file):
        return pd.read_csv(file)
    return pd.DataFrame(columns=cols)

def save_csv(df, file):
    df.to_csv(file, index=False)

def get_device_id():
    if "device_id" not in st.session_state:
        raw = f"{st.session_state}_{datetime.now().date()}"
        st.session_state.device_id = hashlib.sha256(raw.encode()).hexdigest()
    return st.session_state.device_id

def generate_attendance_id(att_type, title):
    now = datetime.now()
    if att_type == "Per Subject":
        return f"{now.date()}_{title.replace(' ','_')}_{now.strftime('%H-%M')}"
    return f"{now.strftime('%A')}_{now.date()}_{now.strftime('%H-%M')}"

def generate_token():
    return secrets.token_urlsafe(16)

def valid_token(attendance_id, token):
    tokens = load_csv(TOKENS_FILE, TOKEN_COLUMNS)
    now = datetime.now()
    tokens["created_at"] = pd.to_datetime(tokens["created_at"])
    tokens = tokens[
        (tokens["attendance_id"] == attendance_id) &
        (tokens["token"] == token) &
        ((now - tokens["created_at"]).dt.total_seconds() <= TOKEN_VALIDITY_SECONDS)
    ]
    return not tokens.empty

def create_qr(attendance_id):
    token = generate_token()
    tokens = load_csv(TOKENS_FILE, TOKEN_COLUMNS)
    tokens.loc[len(tokens)] = [attendance_id, token, datetime.now()]
    save_csv(tokens, TOKENS_FILE)

    url = f"{APP_BASE_URL}/?attendance_id={attendance_id}&token={token}"
    img = qrcode.make(url)
    path = f"qr_{attendance_id}.png"
    img.save(path)
    return path

def name_exists(records, attendance_id, name, exclude=None):
    df = records[records["attendance_id"] == attendance_id]
    if exclude:
        df = df[df["matric"] != exclude]
    return normalize_name(name) in df["full_name"].fillna("").apply(normalize_name).values

# ---------------- STUDENT PAGE ----------------
def student_page():
    q = st.query_params
    attendance_id = q.get("attendance_id")
    token = q.get("token")

    if not attendance_id or not token:
        st.info("Scan the QR code displayed in class.")
        return

    sessions = load_csv(SESSIONS_FILE, SESSION_COLUMNS)
    session = sessions[sessions["attendance_id"] == attendance_id]

    if session.empty or session.iloc[0]["status"] != "Active":
        st.error("Attendance is not active.")
        return

    if not valid_token(attendance_id, token):
        st.error("QR code expired. Scan again.")
        return

    st.title(session.iloc[0]["title"])

    name = st.text_input("Full Name")
    matric = st.text_input("Matric Number (11 digits)")

    if st.button("Submit Attendance"):
        if not re.fullmatch(r"\d{11}", matric):
            st.error("Invalid matric number.")
            return

        records = load_csv(RECORDS_FILE, RECORD_COLUMNS)
        device = get_device_id()

        if matric in records[records["attendance_id"] == attendance_id]["matric"].values:
            st.error("Matric already recorded.")
            return

        if device in records[records["attendance_id"] == attendance_id]["device_id"].values:
            st.error("This device already submitted.")
            return

        if name_exists(records, attendance_id, name):
            st.error("Name already recorded.")
            return

        records.loc[len(records)] = [
            attendance_id, name, matric,
            datetime.now(), device
        ]
        save_csv(records, RECORDS_FILE)
        st.success("Attendance recorded.")

    records = load_csv(RECORDS_FILE, RECORD_COLUMNS)
    st.dataframe(records[records["attendance_id"] == attendance_id][
        ["full_name", "matric", "time"]
    ])
    # ---------------- REP LOGIN ----------------
def rep_login():
    st.title("Course Rep Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if u == REP_USERNAME and p == REP_PASSWORD:
            st.session_state.rep_logged = True
            st.rerun()
        else:
            st.error("Invalid login")

# ---------------- REP DASHBOARD ----------------
def rep_dashboard():
    st.title("Course Rep Dashboard")

    st.subheader("Create Attendance")
    att_type = st.selectbox("Type", ["Daily", "Per Subject"])
    title = "Daily Attendance"
    if att_type == "Per Subject":
        title = st.text_input("Course Code")

    if st.button("Create"):
        sessions = load_csv(SESSIONS_FILE, SESSION_COLUMNS)
        att_id = generate_attendance_id(att_type, title)

        if att_id in sessions["attendance_id"].values:
            st.error("Already exists.")
        else:
            sessions.loc[len(sessions)] = [
                att_id, att_type, title, "Active", datetime.now()
            ]
            save_csv(sessions, SESSIONS_FILE)
            st.success("Attendance created.")
            st.rerun()

    sessions = load_csv(SESSIONS_FILE, SESSION_COLUMNS)
    active = sessions[sessions["status"] == "Active"]

    if active.empty:
        st.info("No active attendance.")
        return

    attendance_id = st.selectbox("Active Attendance", active["attendance_id"])

    # Rotating QR
    if "qr_time" not in st.session_state or time.time() - st.session_state.qr_time > TOKEN_VALIDITY_SECONDS:
        st.session_state.qr_path = create_qr(attendance_id)
        st.session_state.qr_time = time.time()

    st.image(st.session_state.qr_path, caption="Valid for 11 seconds")

    st.markdown(
        f"<meta http-equiv='refresh' content='{TOKEN_VALIDITY_SECONDS}'>",
        unsafe_allow_html=True
    )

    if st.button("End Attendance", type="primary"):
        sessions.loc[sessions["attendance_id"] == attendance_id, "status"] = "Ended"
        save_csv(sessions, SESSIONS_FILE)
        st.success("Attendance ended.")
        st.rerun()
    st.subheader("Attendance List")
    records = load_csv(RECORDS_FILE, RECORD_COLUMNS)
    session_records = records[records["attendance_id"] == attendance_id]
    st.dataframe(session_records)

    st.subheader("Add Student Manually")
    n = st.text_input("Name", key="add_n")
    m = st.text_input("Matric (11 digits)", key="add_m")

    if st.button("Add Student"):
        if not re.fullmatch(r"\d{11}", m):
            st.error("Invalid matric.")
            return
        if m in session_records["matric"].values or name_exists(records, attendance_id, n):
            st.error("Duplicate entry.")
            return
        records.loc[len(records)] = [
            attendance_id, n, m, datetime.now(), "REP_MANUAL"
        ]
        save_csv(records, RECORDS_FILE)
        st.success("Added.")
        st.rerun()

    st.subheader("Edit Student")
    old = st.text_input("Old Matric", key="old")
    new_n = st.text_input("New Name", key="new_n")
    new_m = st.text_input("New Matric", key="new_m")

    if st.button("Update"):
        mask = (records["attendance_id"] == attendance_id) & (records["matric"] == old)
        if records[mask].empty:
            st.error("Not found.")
            return
        if new_m != old and new_m in session_records["matric"].values:
            st.error("Duplicate matric.")
            return
        if name_exists(records, attendance_id, new_n, old):
            st.error("Duplicate name.")
            return
        records.loc[mask, ["full_name", "matric"]] = [new_n, new_m]
        save_csv(records, RECORDS_FILE)
        st.success("Updated.")
        st.rerun()

    st.subheader("Delete Student")
    d = st.text_input("Matric to delete", key="del")

    if st.button("Delete"):
        records = records[~((records["attendance_id"] == attendance_id) & (records["matric"] == d))]
        save_csv(records, RECORDS_FILE)
        st.success("Deleted.")
        st.rerun()

# ---------------- ROUTER ----------------
def main():
    if "rep_logged" not in st.session_state:
        st.session_state.rep_logged = False

    page = st.sidebar.selectbox("Page", ["Student", "Course Rep"])

    if page == "Student":
        student_page()
    else:
        if not st.session_state.rep_logged:
            rep_login()
        else:
            rep_dashboard()

if __name__ == "__main__":
    main()
