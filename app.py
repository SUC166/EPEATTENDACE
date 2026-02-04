import streamlit as st
import pandas as pd
import os, re, time, secrets, hashlib
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

TOKEN_LIFETIME = 20

SESSIONS_FILE = "sessions.csv"
RECORDS_FILE = "records.csv"
CODES_FILE = "codes.csv"

REP_USERNAME = "rep"
REP_PASSWORD = "epe100"

SESSION_COLS = ["session_id", "type", "title", "status", "created_at"]
RECORD_COLS = ["session_id", "name", "matric", "time", "device_id"]
CODE_COLS = ["session_id", "code", "created_at"]

def load_csv(file, cols):
    return pd.read_csv(file, dtype=str) if os.path.exists(file) else pd.DataFrame(columns=cols)

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
    if att_type == "Per Subject":
        return f"{course} {d.strftime('%Y-%m-%d %H:%M')}"
    return f"Daily {d.strftime('%Y-%m-%d %H:%M')}"

def gen_code():
    return f"{secrets.randbelow(10000):04d}"
def write_new_code(session_id):
    codes = load_csv(CODES_FILE, CODE_COLS)
    code = gen_code()
    codes.loc[len(codes)] = [session_id, code, now()]
    save_csv(codes, CODES_FILE)
    return code

def get_latest_code(session_id):
    codes = load_csv(CODES_FILE, CODE_COLS)
    codes = codes[codes["session_id"] == str(session_id)]
    if codes.empty:
        return None
    codes["created_at"] = pd.to_datetime(codes["created_at"])
    return codes.sort_values("created_at").iloc[-1]

def code_valid(session_id, entered_code):
    latest = get_latest_code(session_id)
    if latest is None:
        return False
    age = (datetime.now() - latest["created_at"]).total_seconds()
    return str(entered_code).zfill(4) == str(latest["code"]).zfill(4) and age <= TOKEN_LIFETIME

def student_page():
    sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
    active = sessions[sessions["status"] == "Active"]

    if active.empty:
        st.info("No active attendance.")
        return

    session = active.iloc[-1]
    sid = session["session_id"]

    if "active_session" not in st.session_state:
        st.session_state.active_session = None

    if st.session_state.active_session != sid:
        st.title("Enter Attendance Code")
        code = st.text_input("4-Digit Live Code")

        if st.button("Continue"):
            if not code_valid(sid, code):
                st.error("Invalid or expired code.")
                return
            st.session_state.active_session = sid
            st.rerun()
        return

    # Attendance info
    st.markdown("### 📘 Attendance Details")
    st.write(f"**Title / Course:** {session['title']}")
    st.write(f"**Date:** {session['created_at'].split(' ')[0]}")
    st.divider()

    st.caption("📌 Naming format: **Surname Firstname Middlename**")
    name = st.text_input("Full Name (Surname Firstname Middlename)")
    matric = st.text_input("Matric Number (11 digits)")

    if st.button("Submit Attendance"):
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

        if device_id() in records[records["session_id"] == sid]["device_id"].values:
            st.error("One entry per device.")
            return

        records.loc[len(records)] = [sid, name, matric, now(), device_id()]
        save_csv(records, RECORDS_FILE)
        st.success("Attendance recorded.")

    st.divider()
    st.caption("💙 made with love EPE2025/26")
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

def rep_dashboard():
    st_autorefresh(interval=1000, key="refresh")
    st.title("Course Rep Dashboard")

    att_type = st.selectbox("Attendance Type", ["Daily", "Per Subject"])
    course = st.text_input("Course Code") if att_type == "Per Subject" else ""

    if st.button("Start Attendance"):
        sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
        sid = str(time.time())
        title = session_title(att_type, course)
        sessions.loc[len(sessions)] = [sid, att_type, title, "Active", now()]
        save_csv(sessions, SESSIONS_FILE)
        write_new_code(sid)
        st.success("Attendance started.")
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
if session["status"] == "Active":
        latest = get_latest_code(sid)
        st.markdown(f"## Live Code: `{latest['code']}`")

        if st.button("🛑 END ATTENDANCE"):
            sessions.loc[sessions["session_id"] == sid, "status"] = "Ended"
            save_csv(sessions, SESSIONS_FILE)

            safe_title = re.sub(r"[^\w\-]", "_", session["title"])
            filename = f"attendance_{safe_title}.csv"
            data[["name", "matric", "time"]].to_csv(filename, index=False)

            st.success(f"Attendance ended. CSV saved as {filename}")
            st.rerun()

    st.subheader("Attendance Records")
    if not data.empty:
        st.dataframe(data[["name", "matric", "time"]])

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
