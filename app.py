import streamlit as st
import pandas as pd
import os
import re
import hashlib
from datetime import datetime
import qrcode

# ---------------- CONFIG ----------------
APP_BASE_URL = "https://epeattendance.streamlit.app"  # CHANGE IF NEEDED

SESSIONS_FILE = "attendance_sessions.csv"
RECORDS_FILE = "attendance_records.csv"

SESSION_COLUMNS = ["attendance_id", "type", "title", "status", "created_at"]
RECORD_COLUMNS = ["attendance_id", "full_name", "matric", "time", "device_id"]

REP_USERNAME = "rep"
REP_PASSWORD = "epe100"

# ---------------- HELPERS ----------------
def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        return pd.read_csv(SESSIONS_FILE)
    return pd.DataFrame(columns=SESSION_COLUMNS)

def save_sessions(df):
    df.to_csv(SESSIONS_FILE, index=False)

def load_records():
    if os.path.exists(RECORDS_FILE):
        return pd.read_csv(RECORDS_FILE)
    return pd.DataFrame(columns=RECORD_COLUMNS)

def save_records(df):
    df.to_csv(RECORDS_FILE, index=False)

def get_device_id():
    if "device_id" not in st.session_state:
        raw = f"{st.session_state}_{datetime.now().date()}"
        st.session_state.device_id = hashlib.sha256(raw.encode()).hexdigest()
    return st.session_state.device_id

def generate_attendance_id(att_type, title):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H-%M")
    day = now.strftime("%A")

    if att_type == "Per Subject":
        return f"{date}_{title}_{time}"
    return f"{day}_{date}_{time}"

def generate_qr(attendance_id):
    url = f"{APP_BASE_URL}/?attendance_id={attendance_id}"
    img = qrcode.make(url)
    path = f"qr_{attendance_id}.png"
    img.save(path)
    return path

# ---------------- STUDENT PAGE ----------------
def student_page():
    params = st.query_params
    attendance_id = params.get("attendance_id")

    if not attendance_id:
        st.info("Scan the QR code displayed in class to mark attendance.")
        return

    sessions = load_sessions()
    session = sessions[sessions["attendance_id"] == attendance_id]

    if session.empty:
        st.error("Invalid attendance QR code.")
        return

    if session.iloc[0]["status"] != "Active":
        st.error("Attendance has been closed.")
        return

    st.title(session.iloc[0]["title"])
    st.caption("Attendance is active")

    name = st.text_input("Full Name")
    matric = st.text_input("Matric Number (11 digits)")

    if st.button("Submit Attendance"):
        name = name.strip()
        matric = matric.strip()

        if not name or not matric:
            st.error("All fields are required.")
            return

        if not re.fullmatch(r"\d{11}", matric):
            st.error("Matric number must be exactly 11 digits.")
            return

        records = load_records()
        device_id = get_device_id()

        if device_id in records["device_id"].values:
            st.error("This device has already submitted attendance.")
            return

        if matric in records["matric"].values:
            st.error("This matric number has already been recorded.")
            return

        new = {
            "attendance_id": attendance_id,
            "full_name": name,
            "matric": matric,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": device_id
        }

        save_records(pd.concat([records, pd.DataFrame([new])], ignore_index=True))
        st.success("Attendance recorded successfully.")

    st.subheader("Current Attendance List")
    records = load_records()
    st.dataframe(
        records[records["attendance_id"] == attendance_id][
            ["full_name", "matric", "time"]
        ],
        use_container_width=True
    )

# ---------------- COURSE REP LOGIN ----------------
def rep_login():
    st.title("Course Rep Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == REP_USERNAME and password == REP_PASSWORD:
            st.session_state.rep_logged_in = True
        else:
            st.error("Invalid login details")

# ---------------- COURSE REP DASHBOARD ----------------
def rep_dashboard():
    st.title("Course Rep Dashboard")

    st.subheader("Create Attendance")
    att_type = st.selectbox("Attendance Type", ["Daily", "Per Subject"])
    title = "Daily Attendance"

    if att_type == "Per Subject":
        title = st.text_input("Course Code (e.g IGB101)")

    if st.button("Create Attendance"):
        if att_type == "Per Subject" and not title.strip():
            st.error("Course code is required.")
            return

        attendance_id = generate_attendance_id(att_type, title)
        sessions = load_sessions()

        if attendance_id in sessions["attendance_id"].values:
            st.error("Attendance already exists.")
            return

        new = {
            "attendance_id": attendance_id,
            "type": att_type,
            "title": title if att_type == "Per Subject" else "Daily Attendance",
            "status": "Active",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        save_sessions(pd.concat([sessions, pd.DataFrame([new])], ignore_index=True))
        st.success("Attendance created")
        st.image(generate_qr(attendance_id), caption="Students scan this QR")

    st.divider()

    sessions = load_sessions()
    active = sessions[sessions["status"] == "Active"]

    if active.empty:
        st.info("No active attendance.")
        return

    attendance_id = st.selectbox("Active Attendance", active["attendance_id"])

    st.subheader("Mark Yourself Present")
    m_name = st.text_input("Your Full Name")
    m_matric = st.text_input("Your Matric Number")

    if st.button("Mark Present"):
        records = load_records()

        if m_matric in records["matric"].values:
            st.error("Already recorded.")
            return

        new = {
            "attendance_id": attendance_id,
            "full_name": m_name.strip(),
            "matric": m_matric.strip(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": "MANUAL"
        }

        save_records(pd.concat([records, pd.DataFrame([new])], ignore_index=True))
        st.success("Marked present")

    if st.button("End Attendance"):
        sessions.loc[sessions["attendance_id"] == attendance_id, "status"] = "Ended"
        save_sessions(sessions)
        st.success("Attendance ended. QR code is now invalid.")

# ---------------- ROUTER ----------------
def main():
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Go to", ["Student", "Course Rep"])

    if "rep_logged_in" not in st.session_state:
        st.session_state.rep_logged_in = False

    if page == "Student":
        student_page()
    else:
        if not st.session_state.rep_logged_in:
            rep_login()
        else:
            rep_dashboard()

if __name__ == "__main__":
    main()
