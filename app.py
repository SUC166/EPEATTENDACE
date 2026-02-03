import streamlit as st
import pandas as pd
import os
import re
import hashlib
import secrets
import time
from datetime import datetime
import qrcode

# ================== CONFIG ==================
APP_URL = "https://your-app-name.streamlit.app"  # CHANGE AFTER DEPLOY

SESSIONS_FILE = "sessions.csv"
RECORDS_FILE = "records.csv"
TOKENS_FILE = "tokens.csv"

TOKEN_LIFETIME = 11

REP_USERNAME = "rep"
REP_PASSWORD = "epe100"

SESSION_COLS = ["session_id", "type", "title", "status", "created_at"]
RECORD_COLS = ["session_id", "name", "matric", "time", "device_id"]
TOKEN_COLS = ["session_id", "token", "created_at"]

# ================== HELPERS ==================
def load_csv(file, cols):
    if os.path.exists(file):
        return pd.read_csv(file)
    return pd.DataFrame(columns=cols)

def save_csv(df, file):
    df.to_csv(file, index=False)

def normalize(txt):
    return re.sub(r"\s+", " ", str(txt).strip()).lower()

def wat_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_device_id():
    if "device_id" not in st.session_state:
        raw = f"{st.session_state}{time.time()}"
        st.session_state.device_id = hashlib.sha256(raw.encode()).hexdigest()
    return st.session_state.device_id

def generate_session_title(att_type, course=""):
    now = datetime.now()
    day = now.strftime("%A")
    date = now.strftime("%Y-%m-%d")
    time_ = now.strftime("%H:%M")

    if att_type == "Daily":
        return f"{day} {date} {time_}"
    return f"{day} {course} {date} {time_}"

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

def token_valid(session_id, token):
    tokens = load_csv(TOKENS_FILE, TOKEN_COLS)
    if tokens.empty:
        return False

    tokens["created_at"] = pd.to_datetime(tokens["created_at"])
    now = datetime.now()

    valid = tokens[
        (tokens["session_id"] == session_id) &
        (tokens["token"] == token) &
        ((now - tokens["created_at"]).dt.total_seconds() <= TOKEN_LIFETIME)
    ]
    return not valid.empty

# ================== LIVE QR (NO RELOAD) ==================
def live_qr(session_id):
    qr_box = st.empty()
    timer_box = st.empty()

    while True:
        sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
        status = sessions.loc[
            sessions["session_id"] == session_id, "status"
        ].values[0]

        if status != "Active":
            qr_box.empty()
            timer_box.info("Attendance ended.")
            break

        qr = create_qr(session_id)
        qr_box.image(qr, caption="QR refreshes every 11 seconds")

        for i in range(TOKEN_LIFETIME, 0, -1):
            timer_box.caption(f"Refreshing in {i} seconds…")
            time.sleep(1)

# ================== STUDENT PAGE ==================
def student_page():
    q = st.query_params
    session_id = q.get("session_id")
    token = q.get("token")

    if not session_id or not token:
        st.info("Scan the QR code displayed in class.")
        return

    sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
    session = sessions[sessions["session_id"] == session_id]

    if session.empty or session.iloc[0]["status"] != "Active":
        st.error("Attendance not active.")
        return

    if not token_valid(session_id, token):
        st.error("QR expired. Scan again.")
        return

    st.title(session.iloc[0]["title"])

    name = st.text_input("Full Name")
    matric = st.text_input("Matric Number (11 digits)")

    if st.button("Submit"):
        if not re.fullmatch(r"\d{11}", matric):
            st.error("Invalid matric number.")
            return

        records = load_csv(RECORDS_FILE, RECORD_COLS)
        device = get_device_id()
        session_records = records[records["session_id"] == session_id]

        if device in session_records["device_id"].values:
            st.error("One entry per device only.")
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

# ================== REP LOGIN ==================
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

# ================== REP DASHBOARD ==================
def rep_dashboard():
    st.title("Course Rep Dashboard")

    st.subheader("Start Attendance Session")
    att_type = st.selectbox("Attendance Type", ["Daily", "Per Subject"])
    course = ""
    if att_type == "Per Subject":
        course = st.text_input("Course Code (e.g FRN101)")

    if st.button("Start Session"):
        if att_type == "Per Subject" and not course:
            st.error("Course code required.")
            return

        sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
        session_id = str(time.time())
        title = generate_session_title(att_type, course)

        sessions.loc[len(sessions)] = [
            session_id, att_type, title, "Active", wat_now()
        ]
        save_csv(sessions, SESSIONS_FILE)
        st.success("Attendance started.")
        st.rerun()

    sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
    if sessions.empty:
        return

    session_id = st.selectbox(
        "Select Session",
        sessions["session_id"],
        format_func=lambda x: sessions[sessions["session_id"] == x]["title"].iloc[0]
    )

    session = sessions[sessions["session_id"] == session_id].iloc[0]

    if session["status"] == "Active":
        st.subheader("Live QR Code")
        live_qr(session_id)

    records = load_csv(RECORDS_FILE, RECORD_COLS)
    session_records = records[records["session_id"] == session_id]

    st.subheader("Attendance Records")
    edited = st.data_editor(session_records, use_container_width=True)

    if st.button("Save Changes"):
        records = records[records["session_id"] != session_id]
        records = pd.concat([records, edited], ignore_index=True)
        save_csv(records, RECORDS_FILE)
        st.success("Records updated.")
        st.rerun()

    st.download_button(
        "Download CSV",
        data=edited.to_csv(index=False),
        file_name=f"{session['title']}.csv",
        mime="text/csv"
    )

    if st.button("End Attendance"):
        sessions.loc[sessions["session_id"] == session_id, "status"] = "Ended"
        save_csv(sessions, SESSIONS_FILE)
        st.success("Attendance ended.")
        st.rerun()

# ================== ROUTER ==================
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
