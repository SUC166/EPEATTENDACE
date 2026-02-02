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
APP_BASE_URL = "https://epeattendance.streamlit.app"  # CHANGE IF NEEDED

SESSIONS_FILE = "attendance_sessions.csv"
RECORDS_FILE = "attendance_records.csv"

# Rotating QR tokens
TOKENS_FILE = "attendance_tokens.csv"
TOKEN_VALIDITY_SECONDS = 11

SESSION_COLUMNS = ["attendance_id", "type", "title", "status", "created_at"]
RECORD_COLUMNS = ["attendance_id", "full_name", "matric", "time", "device_id"]
TOKEN_COLUMNS = ["attendance_id", "token", "created_at"]

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

def load_tokens():
    if os.path.exists(TOKENS_FILE):
        return pd.read_csv(TOKENS_FILE)
    return pd.DataFrame(columns=TOKEN_COLUMNS)

def save_tokens(df):
    df.to_csv(TOKENS_FILE, index=False)

def get_device_id():
    if "device_id" not in st.session_state:
        raw = f"{st.session_state}_{datetime.now().date()}"
        st.session_state.device_id = hashlib.sha256(raw.encode()).hexdigest()
    return st.session_state.device_id

def generate_attendance_id(att_type, title):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M")
    day = now.strftime("%A")

    if att_type == "Per Subject":
        safe_title = title.replace(" ", "_").strip()
        return f"{date}_{safe_title}_{time_str}"
    return f"{day}_{date}_{time_str}"

def generate_token():
    return secrets.token_urlsafe(16)

def cleanup_old_tokens(df):
    """Keep only tokens that are not expired."""
    if df.empty:
        return df

    now = datetime.now()
    keep = []

    for _, row in df.iterrows():
        try:
            created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
        except:
            continue

        if (now - created).total_seconds() <= TOKEN_VALIDITY_SECONDS:
            keep.append(row)

    if not keep:
        return pd.DataFrame(columns=TOKEN_COLUMNS)

    return pd.DataFrame(keep)

def create_rotating_qr(attendance_id):
    """Create a fresh QR token valid for 11 seconds."""
    tokens = load_tokens()
    tokens = cleanup_old_tokens(tokens)

    token = generate_token()
    new = {
        "attendance_id": attendance_id,
        "token": token,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    tokens = pd.concat([tokens, pd.DataFrame([new])], ignore_index=True)
    save_tokens(tokens)

    url = f"{APP_BASE_URL}/?attendance_id={attendance_id}&token={token}"
    img = qrcode.make(url)

    path = f"qr_{attendance_id}.png"
    img.save(path)
    return path

def is_valid_token(attendance_id, token):
    tokens = load_tokens()
    tokens = cleanup_old_tokens(tokens)

    valid = tokens[
        (tokens["attendance_id"] == attendance_id) &
        (tokens["token"] == token)
    ]
    return not valid.empty

# ---------------- STUDENT PAGE ----------------
def student_page():
    params = st.query_params
    attendance_id = params.get("attendance_id")
    token = params.get("token")

    if not attendance_id:
        st.info("Scan the QR code displayed in class to mark attendance.")
        return

    if not token:
        st.error("Invalid or missing QR token. Please scan again.")
        return

    sessions = load_sessions()
    session = sessions[sessions["attendance_id"] == attendance_id]

    if session.empty:
        st.error("Invalid attendance QR code.")
        return

    if session.iloc[0]["status"] != "Active":
        st.error("Attendance has been closed.")
        return

    # Validate rotating token
    if not is_valid_token(attendance_id, token):
        st.error("QR code expired. Please scan the latest QR code in class.")
        return

    st.title(session.iloc[0]["title"])
    st.caption("Attendance is active (QR changes every 11 seconds)")

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

        # Check duplicates only within this attendance session
        this_session = records[records["attendance_id"] == attendance_id]

        if device_id in this_session["device_id"].values:
            st.error("This device has already submitted attendance for this session.")
            return

        if matric in this_session["matric"].values:
            st.error("This matric number has already been recorded for this session.")
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

    # --- Create Attendance ---
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

    st.divider()

    # --- Select Active Attendance ---
    sessions = load_sessions()
    active = sessions[sessions["status"] == "Active"]

    if active.empty:
        st.info("No active attendance.")
        return

    attendance_id = st.selectbox("Active Attendance", active["attendance_id"])

    # ---------------- ROTATING QR (NON-BLOCKING) ----------------
    st.subheader("Live QR Code (changes every 11 seconds)")
    st.caption("Students must scan the latest QR code. Old links expire automatically.")

    if "last_qr_time" not in st.session_state:
        st.session_state.last_qr_time = 0

    if "current_qr_path" not in st.session_state:
        st.session_state.current_qr_path = None

    now = time.time()
    if (now - st.session_state.last_qr_time) >= TOKEN_VALIDITY_SECONDS or st.session_state.current_qr_path is None:
        st.session_state.current_qr_path = create_rotating_qr(attendance_id)
        st.session_state.last_qr_time = now

    st.image(st.session_state.current_qr_path, caption="Valid for 11 seconds")

    # Auto-refresh the page every 11 seconds without blocking buttons
    st.markdown(
        f"""
        <script>
        setTimeout(function(){{
            window.location.reload();
        }}, {TOKEN_VALIDITY_SECONDS * 1000});
        </script>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    # ---------------- REP ACTIONS ----------------
    st.subheader("Rep Actions")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("End Attendance", type="primary"):
            sessions = load_sessions()
            sessions.loc[sessions["attendance_id"] == attendance_id, "status"] = "Ended"
            save_sessions(sessions)
            st.success("Attendance ended. QR code is now invalid.")
            st.rerun()

    with col2:
        if st.button("Refresh List"):
            st.rerun()

    st.divider()

    # ---------------- VIEW CURRENT LIST ----------------
    st.subheader("Current Attendance List (Rep View)")
    records = load_records()
    this_session = records[records["attendance_id"] == attendance_id].copy()

    if this_session.empty:
        st.info("No students have marked attendance yet.")
    else:
        st.dataframe(
            this_session[["full_name", "matric", "time", "device_id"]],
            use_container_width=True
        )

    st.divider()

    # ---------------- MANUAL ADD ----------------
    st.subheader("Add Student Manually (Rep Only)")
    m_name = st.text_input("Student Full Name", key="manual_name")
    m_matric = st.text_input("Student Matric Number (11 digits)", key="manual_matric")

    if st.button("Add Student"):
        m_name = m_name.strip()
        m_matric = m_matric.strip()

        if not m_name or not m_matric:
            st.error("Name and matric number are required.")
            return

        if not re.fullmatch(r"\d{11}", m_matric):
            st.error("Matric number must be exactly 11 digits.")
            return

        records = load_records()
        this_session = records[records["attendance_id"] == attendance_id]

        if m_matric in this_session["matric"].values:
            st.error("That matric number is already recorded for this attendance.")
            return

        new = {
            "attendance_id": attendance_id,
            "full_name": m_name,
            "matric": m_matric,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "device_id": "MANUAL_REP"
        }

        save_records(pd.concat([records, pd.DataFrame([new])], ignore_index=True))
        st.success("Student added successfully.")
        st.rerun()

    st.divider()

    # ---------------- DELETE STUDENT ----------------
    st.subheader("Delete Student From List (Rep Only)")
    del_matric = st.text_input("Enter Matric Number to Delete", key="delete_matric")

    if st.button("Delete Student"):
        del_matric = del_matric.strip()

        if not re.fullmatch(r"\d{11}", del_matric):
            st.error("Matric number must be exactly 11 digits.")
            return

        records = load_records()
        before = len(records)

        # delete only within selected attendance
        records = records[~((records["attendance_id"] == attendance_id) & (records["matric"] == del_matric))]

        after = len(records)

        if before == after:
            st.error("No student with that matric number was found in this attendance list.")
            return

        save_records(records)
        st.success("Student deleted successfully.")
        st.rerun()

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
