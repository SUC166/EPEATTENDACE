import streamlit as st
import pandas as pd
import os
import re
import hashlib
import secrets
import time
from datetime import datetime
import qrcode

# ---------------- FILES ----------------
SESSIONS_FILE = "sessions.csv"
RECORDS_FILE = "records.csv"
TOKENS_FILE = "tokens.csv"

# ---------------- CONSTANTS ----------------
TOKEN_VALIDITY = 11
REP_USERNAME = "rep"
REP_PASSWORD = "epe100"

SESSION_COLS = ["session_id", "type", "title", "status", "created_at"]
RECORD_COLS = ["session_id", "name", "matric", "time", "device_id"]
TOKEN_COLS = ["session_id", "token", "created_at"]

APP_URL = "https://your-app-name.streamlit.app"  # change later

# ---------------- HELPERS ----------------
def load_csv(file, cols):
    if os.path.exists(file):
        return pd.read_csv(file)
    return pd.DataFrame(columns=cols)

def save_csv(df, file):
    df.to_csv(file, index=False)

def normalize(text):
    return re.sub(r"\s+", " ", str(text).strip()).lower()

def get_device_id():
    if "device_id" not in st.session_state:
        raw = f"{st.session_state}_{time.time()}"
        st.session_state.device_id = hashlib.sha256(raw.encode()).hexdigest()
    return st.session_state.device_id

def wat_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def generate_session_name(att_type, title=""):
    now = datetime.now()
    day = now.strftime("%A")
    date = now.strftime("%Y-%m-%d")
    time_ = now.strftime("%H:%M")

    if att_type == "Daily":
        return f"{day} {date} {time_}"
    return f"{day} {title} {date} {time_}"

def generate_token():
    return secrets.token_urlsafe(16)

def create_qr(session_id):
    tokens = load_csv(TOKENS_FILE, TOKEN_COLS)
    token = generate_token()
    tokens.loc[len(tokens)] = [session_id, token, wat_now()]
    save_csv(tokens, TOKENS_FILE)

    url = f"{APP_URL}/?session_id={session_id}&token={token}"
    img = qrcode.make(url)
    path = f"qr_{session_id}.png"
    img.save(path)
    return path

def valid_token(session_id, token):
    tokens = load_csv(TOKENS_FILE, TOKEN_COLS)
    if tokens.empty:
        return False

    tokens["created_at"] = pd.to_datetime(tokens["created_at"])
    now = datetime.now()

    valid = tokens[
        (tokens["session_id"] == session_id) &
        (tokens["token"] == token) &
        ((now - tokens["created_at"]).dt.total_seconds() <= TOKEN_VALIDITY)
    ]
    return not valid.empty
    # ---------------- STUDENT PAGE ----------------
def student_page():
    q = st.query_params
    session_id = q.get("session_id")
    token = q.get("token")

    if not session_id or not token:
        st.info("Scan the QR code in class to mark attendance.")
        return

    sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
    session = sessions[sessions["session_id"] == session_id]

    if session.empty or session.iloc[0]["status"] != "Active":
        st.error("Attendance is closed.")
        return

    if not valid_token(session_id, token):
        st.error("QR code expired. Scan again.")
        return

    st.title(session.iloc[0]["title"])

    name = st.text_input("Full Name")
    matric = st.text_input("Matric Number (11 digits)")

    if st.button("Submit Attendance"):
        if not re.fullmatch(r"\d{11}", matric):
            st.error("Invalid matric number.")
            return

        records = load_csv(RECORDS_FILE, RECORD_COLS)
        device = get_device_id()

        session_records = records[records["session_id"] == session_id]

        if device in session_records["device_id"].values:
            st.error("This device has already submitted.")
            return

        if matric in session_records["matric"].values:
            st.error("Matric already recorded.")
            return

        if normalize(name) in session_records["name"].apply(normalize).values:
            st.error("Name already recorded.")
            return

        records.loc[len(records)] = [
            session_id, name, matric, wat_now(), device
        ]
        save_csv(records, RECORDS_FILE)
        st.success("Attendance recorded successfully.")

# ---------------- REP LOGIN ----------------
def rep_login():
    st.title("Course Rep Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if u == REP_USERNAME and p == REP_PASSWORD:
            st.session_state.rep = True
            st.rerun()
        else:
            st.error("Invalid credentials")

# ---------------- SESSION CREATION ----------------
def create_session():
    st.subheader("Create Attendance Session")
    att_type = st.selectbox("Attendance Type", ["Daily", "Per Subject"])

    title = ""
    if att_type == "Per Subject":
        title = st.text_input("Course Code (e.g FRN101)")

    if st.button("Start Attendance"):
        if att_type == "Per Subject" and not title:
            st.error("Course code required.")
            return

        sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
        session_id = f"{time.time()}"
        name = generate_session_name(att_type, title)

        sessions.loc[len(sessions)] = [
            session_id, att_type, name, "Active", wat_now()
        ]
        save_csv(sessions, SESSIONS_FILE)
        st.success("Attendance session started.")
        st.rerun()
        # ---------------- REP DASHBOARD ----------------
def rep_dashboard():
    st.title("Course Rep Dashboard")

    create_session()
    sessions = load_csv(SESSIONS_FILE, SESSION_COLS)

    if sessions.empty:
        st.info("No sessions yet.")
        return

    session_id = st.selectbox(
        "Select Attendance Session",
        sessions["session_id"],
        format_func=lambda x: sessions[sessions["session_id"] == x]["title"].iloc[0]
    )

    session = sessions[sessions["session_id"] == session_id].iloc[0]

    # QR rotation
    if session["status"] == "Active":
        if "qr_time" not in st.session_state or time.time() - st.session_state.qr_time > TOKEN_VALIDITY:
            st.session_state.qr_path = create_qr(session_id)
            st.session_state.qr_time = time.time()

        st.image(st.session_state.qr_path, caption="QR code refreshes every 11 seconds")
        st.markdown(f"<meta http-equiv='refresh' content='{TOKEN_VALIDITY}'>", unsafe_allow_html=True)

    records = load_csv(RECORDS_FILE, RECORD_COLS)
    session_records = records[records["session_id"] == session_id]

    st.subheader("Attendance Records")
    edited = st.data_editor(session_records, num_rows="fixed", use_container_width=True)

    if st.button("Save Edits"):
        # Remove old records for session
        records = records[records["session_id"] != session_id]
        records = pd.concat([records, edited], ignore_index=True)
        save_csv(records, RECORDS_FILE)
        st.success("Changes saved.")
        st.rerun()

    st.download_button(
        "Download CSV",
        data=edited.to_csv(index=False),
        file_name=f"{session['title']}.csv",
        mime="text/csv"
    )

    if st.button("End Attendance Session"):
        sessions.loc[sessions["session_id"] == session_id, "status"] = "Ended"
        save_csv(sessions, SESSIONS_FILE)
        st.success("Attendance ended.")
        st.rerun()

# ---------------- ROUTER ----------------
def main():
    if "rep" not in st.session_state:
        st.session_state.rep = False

    page = st.sidebar.selectbox("Page", ["Student", "Course Rep"])

    if page == "Student":
        student_page()
    else:
        if not st.session_state.rep:
            rep_login()
        else:
            rep_dashboard()

if __name__ == "__main__":
    main()
