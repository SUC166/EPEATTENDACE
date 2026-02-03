import streamlit as st
import pandas as pd
import os, re, time, secrets, hashlib
from datetime import datetime
import qrcode
from streamlit_autorefresh import st_autorefresh

APP_URL = "https://epeattendance.streamlit.app"
TOKEN_LIFETIME = 11

SESSIONS_FILE = "sessions.csv"
RECORDS_FILE = "records.csv"
TOKENS_FILE = "tokens.csv"

REP_USERNAME = "rep"
REP_PASSWORD = "epe100"

SESSION_COLS = ["session_id", "type", "title", "status", "created_at"]
RECORD_COLS = ["session_id", "name", "matric", "time", "device_id"]
TOKEN_COLS = ["session_id", "token", "created_at"]

def load_csv(file, cols):
    return pd.read_csv(file) if os.path.exists(file) else pd.DataFrame(columns=cols)

def save_csv(df, file):
    df.to_csv(file, index=False)

def normalize(txt):
    return re.sub(r"\s+", " ", str(txt).strip()).lower()

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def device_id():
    if "device_id" not in st.session_state:
        raw = f"{time.time()}{secrets.token_hex()}"
        st.session_state.device_id = hashlib.sha256(raw.encode()).hexdigest()
    return st.session_state.device_id

def session_title(att_type, course=""):
    d = datetime.now()
    day = d.strftime("%A")
    date = d.strftime("%Y-%m-%d")
    t = d.strftime("%H:%M")
    return f"{day} {course} {date} {t}" if att_type == "Per Subject" else f"{day} {date} {t}"

def gen_token():
    return secrets.token_urlsafe(16)

def create_qr(session_id):
    tokens = load_csv(TOKENS_FILE, TOKEN_COLS)
    token = gen_token()
    tokens.loc[len(tokens)] = [session_id, token, now()]
    save_csv(tokens, TOKENS_FILE)

    url = f"{APP_URL}/?session_id={session_id}&token={token}"
    img = qrcode.make(url)
    path = f"qr_{session_id}.png"
    img.save(path)
    return path

def token_valid(session_id, token):
    tokens = load_csv(TOKENS_FILE, TOKEN_COLS)
    if tokens.empty: return False
    tokens["created_at"] = pd.to_datetime(tokens["created_at"])
    age = (datetime.now() - tokens["created_at"]).dt.total_seconds()

    valid = tokens[
        (tokens["session_id"] == session_id) &
        (tokens["token"] == token) &
        (age <= TOKEN_LIFETIME)
    ]
    return not valid.empty

def rotating_qr(session_id):
    if "qr_time" not in st.session_state:
        st.session_state.qr_time = 0
        st.session_state.qr_path = None

    elapsed = time.time() - st.session_state.qr_time

    if elapsed >= TOKEN_LIFETIME:
        st.session_state.qr_path = create_qr(session_id)
        st.session_state.qr_time = time.time()
        elapsed = 0

    return st.session_state.qr_path, int(TOKEN_LIFETIME - elapsed)

# ================= STUDENT =================
def student_page():
    q = st.query_params
    session_id = q.get("session_id")
    token = q.get("token")

    if not session_id or not token:
        st.info("Scan QR in class.")
        return

    sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
    session = sessions[sessions["session_id"] == session_id]

    if session.empty or session.iloc[0]["status"] != "Active":
        st.error("Attendance closed.")
        return

    if not token_valid(session_id, token):
        st.error("QR expired. Rescan.")
        return

    st.title(session.iloc[0]["title"])

    name = st.text_input("Full Name")
    matric = st.text_input("Matric Number (11 digits)")

    if st.button("Submit"):
        if not re.fullmatch(r"\d{11}", matric):
            st.error("Invalid matric number.")
            return

        records = load_csv(RECORDS_FILE, RECORD_COLS)

        if normalize(name) in records["name"].apply(normalize).values:
            st.error("Name already exists.")
            return

        if matric in records["matric"].values:
            st.error("Matric already used.")
            return

        dev = device_id()
        if dev in records[records["session_id"] == session_id]["device_id"].values:
            st.error("One entry per device.")
            return

        records.loc[len(records)] = [session_id, name, matric, now(), dev]
        save_csv(records, RECORDS_FILE)
        st.success("Attendance recorded.")

# ================= REP LOGIN =================
def rep_login():
    st.title("Course Rep Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if u == REP_USERNAME and p == REP_PASSWORD:
            st.session_state.rep = True
            st.rerun()
        else:
            st.error("Wrong login")

# ================= REP DASHBOARD =================
def rep_dashboard():
    st_autorefresh(interval=1000, key="qr_refresh")

    st.title("Course Rep Dashboard")

    att_type = st.selectbox("Attendance Type", ["Daily", "Per Subject"])
    course = st.text_input("Course Code") if att_type == "Per Subject" else ""

    if st.button("Start Session"):
        sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
        sid = str(time.time())
        title = session_title(att_type, course)

        sessions.loc[len(sessions)] = [sid, att_type, title, "Active", now()]
        save_csv(sessions, SESSIONS_FILE)
        st.success("Session started.")
        st.rerun()

    sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
    if sessions.empty:
        return

    sid = st.selectbox(
        "Select Session",
        sessions["session_id"],
        format_func=lambda x: sessions[sessions["session_id"] == x]["title"].iloc[0]
    )

    session = sessions[sessions["session_id"] == sid].iloc[0]
    records = load_csv(RECORDS_FILE, RECORD_COLS)
    data = records[records["session_id"] == sid]

    st.subheader("Attendance Records")

    if not data.empty:
        st.dataframe(data[["name", "matric", "time"]])

    st.download_button(
        "Download CSV",
        data=data[["name", "matric", "time"]].to_csv(index=False),
        file_name=f"{session['title']}.csv"
    )

    if session["status"] == "Active":
        st.subheader("Live QR")
        qr, remaining = rotating_qr(sid)
        if qr:
            st.image(qr, caption=f"Refresh in {remaining}s")

# ================= MAIN =================
def main():
    if "rep" not in st.session_state:
        st.session_state.rep = False

    page = st.sidebar.selectbox("Page", ["Student", "Course Rep"])

    if page == "Student":
        student_page()
    else:
        rep_login() if not st.session_state.rep else rep_dashboard()

if __name__ == "__main__":
    main()
