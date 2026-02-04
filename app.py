import streamlit as st
import pandas as pd
import os, re, time, secrets, hashlib
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

TOKEN_LIFETIME = 20

# ===== CHANGE THIS =====
DEPARTMENT = "EPE"

# ===== LOGIN HASHES =====
REP_USERNAME_HASH = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
REP_PASSWORD_HASH = "d74ff0ee8da3b9806b18c877dbf29bbde50b5bd8e4dad7a3a725000feb82e8f1"

SESSIONS_FILE = "sessions.csv"
RECORDS_FILE = "records.csv"
CODES_FILE = "codes.csv"

SESSION_COLS = ["session_id", "type", "title", "status", "created_at", "department"]
RECORD_COLS = ["session_id", "name", "matric", "time", "device_id", "department"]
CODE_COLS = ["session_id", "code", "created_at"]

# ==================================
# ✅ GLOBAL TIME FIX (+1 HOUR)
# ==================================
def now_dt():
    """Returns current time +1 hour (fixes server lag)."""
    return datetime.now() + timedelta(hours=1)

def now():
    """String time saved in CSV."""
    return now_dt().strftime("%Y-%m-%d %H:%M:%S")
def load_csv(file, cols):
    return pd.read_csv(file, dtype=str) if os.path.exists(file) else pd.DataFrame(columns=cols)

def save_csv(df, file):
    df.to_csv(file, index=False)

def normalize(txt):
    return re.sub(r"\s+", " ", str(txt).strip()).lower()

def sha256_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()

def device_id():
    if "device_id" not in st.session_state:
        raw = f"{time.time()}{secrets.token_hex()}"
        st.session_state.device_id = hashlib.sha256(raw.encode()).hexdigest()
    return st.session_state.device_id

def session_title(att_type, course=""):
    d = now_dt()
    base = d.strftime("%Y-%m-%d %H:%M")
    if att_type == "Per Subject":
        return f"{DEPARTMENT} - {course} {base}"
    return f"{DEPARTMENT} - Daily {base}"

def gen_code():
    return f"{secrets.randbelow(10000):04d}"

def write_new_code(session_id):
    codes = load_csv(CODES_FILE, CODE_COLS)
    code = gen_code()
    codes.loc[len(codes)] = [session_id, code, now()]
    save_csv(codes, CODES_FILE)
    return code

def parse_time(ts):
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except:
        return None

def get_latest_code(session_id):
    codes = load_csv(CODES_FILE, CODE_COLS)
    codes = codes[codes["session_id"] == str(session_id)]
    if codes.empty:
        return None
    codes = codes.sort_values("created_at")
    return codes.iloc[-1]

def code_valid(session_id, entered_code):
    latest = get_latest_code(session_id)
    if latest is None:
        return False

    t = parse_time(latest["created_at"])
    if t is None:
        return False

    age = (now_dt() - t).total_seconds()
    return str(entered_code).zfill(4) == str(latest["code"]).zfill(4) and age <= TOKEN_LIFETIME

def rep_live_code(session_id):
    latest = get_latest_code(session_id)

    if latest is None:
        return write_new_code(session_id), TOKEN_LIFETIME

    t = parse_time(latest["created_at"])
    if t is None:
        return write_new_code(session_id), TOKEN_LIFETIME

    age = (now_dt() - t).total_seconds()
    if age >= TOKEN_LIFETIME:
        return write_new_code(session_id), TOKEN_LIFETIME

    return latest["code"], int(TOKEN_LIFETIME - age)
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

    st.markdown("### Attendance Details")
    st.write(f"Department: {session['department']}")
    st.write(f"Title: {session['title']}")
    st.write(f"Date: {session['created_at'].split(' ')[0]}")
    st.divider()

    name = st.text_input("Full Name")
    matric = st.text_input("Matric Number")

    if st.button("Submit Attendance"):
        if not re.fullmatch(r"\d{11}", str(matric)):
            st.error("Matric must be 11 digits.")
            return

        records = load_csv(RECORDS_FILE, RECORD_COLS)
        session_records = records[records["session_id"] == sid]

        if normalize(name) in session_records["name"].apply(normalize).values:
            st.error("Name already exists.")
            return

        if matric in session_records["matric"].values:
            st.error("Matric already used.")
            return

        if device_id() in session_records["device_id"].values:
            st.error("One entry per device.")
            return

        records.loc[len(records)] = [sid, name, matric, now(), device_id(), DEPARTMENT]
        save_csv(records, RECORDS_FILE)
        st.success("Attendance recorded.")
def rep_login():
    st.title("Course Rep Login")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if sha256_hash(u) == REP_USERNAME_HASH and sha256_hash(p) == REP_PASSWORD_HASH:
            st.session_state.rep = True
            st.success("Login successful.")
            st.rerun()
        else:
            st.error("Invalid credentials.")

def rep_dashboard():
    st_autorefresh(interval=1000, key="refresh")
    st.title(f"{DEPARTMENT} Rep Dashboard")

    sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
    records = load_csv(RECORDS_FILE, RECORD_COLS)

    att_type = st.selectbox("Attendance Type", ["Daily", "Per Subject"])
    course = st.text_input("Course Code") if att_type == "Per Subject" else ""

    if st.button("Start Attendance"):
        if not sessions[sessions["status"] == "Active"].empty:
            st.error("End current attendance first.")
        else:
            sid = str(time.time())
            sessions.loc[len(sessions)] = [
                sid, att_type, session_title(att_type, course),
                "Active", now(), DEPARTMENT
            ]
            save_csv(sessions, SESSIONS_FILE)
            write_new_code(sid)
            st.success("Attendance started.")
            st.rerun()

    active = sessions[sessions["status"] == "Active"]
    if active.empty:
        return

    session = active.iloc[-1]
    sid = session["session_id"]

    code, remaining = rep_live_code(sid)
    st.markdown(f"## Live Code: `{code}`")
    st.caption(f"Changes in {remaining}s")

    if st.button("END ATTENDANCE"):
        sessions.loc[sessions["session_id"] == sid, "status"] = "Ended"
        save_csv(sessions, SESSIONS_FILE)
        st.success("Attendance ended.")
        st.rerun()

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
