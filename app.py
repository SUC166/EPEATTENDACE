import streamlit as st
import pandas as pd
import os
import re
import uuid
import hashlib
from datetime import datetime
import qrcode

# ---------------- CONFIG ----------------
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
        st.session_state.device_id = hashlib.sha256(
            str(uuid.uuid4()).encode()
        ).hexdigest()
    return st.session_state.device_id

def generate_qr(attendance_id):
    url = f"?attendance_id={attendance_id}"
    img = qrcode.make(url)
    path = f"qr_{attendance_id}.png"
    img.save(path)
    return path

# ---------------- STUDENT PAGE ----------------
def student_page():
    params = st.query_params
    attendance_id = params.get("attendance_id")

    if not attendance_id:
        st.error("Invalid or missing attendance QR code.")
        return

    sessions = load_sessions()
    session = sessions[sessions["attendance_id"] == attendance_id]

    if session.empty or session.iloc[0]["status"] != "Active":
        st.error("Attendance is closed.")
        return

    st.title(session.iloc[0]["title"])

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

        new_record = {
            "attendance_id": attendance_id,
            "full_name": name,
            "matric": matric,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": device_id
        }

        records = pd.concat([records, pd.DataFrame([new_record])], ignore_index=True)
        save_records(records)
        st.success("Attendance recorded successfully.")

# ---------------- COURSE REP LOGIN ----------------
def rep_login():
    st.title("Course Rep Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == REP_USERNAME and password == REP_PASSWORD:
            st.session_state.rep_logged_in = True
        else:
            st.error("Invalid credentials")

# ---------------- COURSE REP DASHBOARD ----------------
def rep_dashboard():
    st.title("Course Rep Dashboard")

    # CREATE ATTENDANCE
    st.subheader("Create Attendance")
    att_type = st.selectbox("Attendance Type", ["Daily", "Per Subject"])
    title = "Daily Attendance"

    if att_type == "Per Subject":
        title = st.text_input("Course Code (e.g EPE101)")

    if st.button("Create Attendance"):
        if att_type == "Per Subject" and not title.strip():
            st.error("Course code required.")
        else:
            sessions = load_sessions()
            attendance_id = str(uuid.uuid4())

            new_session = {
                "attendance_id": attendance_id,
                "type": att_type,
                "title": title,
                "status": "Active",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            sessions = pd.concat([sessions, pd.DataFrame([new_session])], ignore_index=True)
            save_sessions(sessions)

            qr_path = generate_qr(attendance_id)
            st.success("Attendance created.")
            st.image(qr_path, caption="Students scan this QR")

    st.divider()

    # END ATTENDANCE
    sessions = load_sessions()
    active = sessions[sessions["status"] == "Active"]

    if not active.empty:
        selected = st.selectbox(
            "Active Attendances",
            active["title"] + " | " + active["attendance_id"]
        )

        if st.button("End Attendance"):
            att_id = selected.split("|")[-1].strip()
            sessions.loc[sessions["attendance_id"] == att_id, "status"] = "Ended"
            save_sessions(sessions)
            st.success("Attendance ended.")

    st.divider()

    # EDIT ATTENDANCE RECORDS
    st.subheader("Edit Attendance Records")

    records = load_records()
    if records.empty:
        st.info("No attendance records yet.")
        return

    edited = st.data_editor(records, num_rows="fixed", use_container_width=True)

    if st.button("Save Changes"):
        if edited["matric"].duplicated().any():
            st.error("Duplicate matric numbers detected.")
            return

        if not edited["matric"].apply(lambda x: bool(re.fullmatch(r"\d{11}", str(x)))).all():
            st.error("All matric numbers must be 11 digits.")
            return

        save_records(edited)
        st.success("Changes saved.")

    st.download_button(
        "Download Attendance CSV",
        data=records.to_csv(index=False),
        file_name="attendance_records.csv",
        mime="text/csv"
    )

# ---------------- ROUTER ----------------
def main():
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Go to", ["Student Attendance", "Course Rep"])

    if "rep_logged_in" not in st.session_state:
        st.session_state.rep_logged_in = False

    if page == "Student Attendance":
        student_page()
    else:
        if not st.session_state.rep_logged_in:
            rep_login()
        else:
            rep_dashboard()

if __name__ == "__main__":
    main()
