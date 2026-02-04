import streamlit as st
import pandas as pd
import os, re, time, secrets, hashlib
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh

TOKEN_LIFETIME = 20

# ===== CHANGE THIS DEPARTMENT =====
DEPARTMENT = "EPE"

# ===== REPLACE WITH YOUR HASHES =====
REP_USERNAME_HASH = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
REP_PASSWORD_HASH = "d74ff0ee8da3b9806b18c877dbf29bbde50b5bd8e4dad7a3a725000feb82e8f1"

SESSIONS_FILE = "sessions.csv"
RECORDS_FILE = "records.csv"
CODES_FILE = "codes.csv"

SESSION_COLS = ["session_id", "type", "title", "status", "created_at", "department"]
RECORD_COLS = ["session_id", "name", "matric", "time", "device_id", "department"]
CODE_COLS = ["session_id", "code", "created_at"]

# ==============================
# ✅ TIMEZONE FIX (Nigeria/WAT)
# WAT = UTC+1
# ==============================
WAT = timezone(timedelta(hours=1))

def local_now_dt():
    """Timezone-aware datetime in WAT (Nigeria)."""
    return datetime.now(WAT)

def now():
    """String timestamp stored in CSV (WAT)."""
    return local_now_dt().strftime("%Y-%m-%d %H:%M:%S")
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
    d = local_now_dt()
    base = f"{d.strftime('%Y-%m-%d %H:%M')}"
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

def get_latest_code(session_id):
    codes = load_csv(CODES_FILE, CODE_COLS)
    codes = codes[codes["session_id"] == str(session_id)]
    if codes.empty:
        return None

    # parse and force WAT timezone
    codes["created_at"] = pd.to_datetime(codes["created_at"], errors="coerce")
    codes["created_at"] = codes["created_at"].dt.tz_localize(WAT, nonexistent="shift_forward", ambiguous="NaT")

    return codes.sort_values("created_at").iloc[-1]

def code_valid(session_id, entered_code):
    latest = get_latest_code(session_id)
    if latest is None or pd.isna(latest["created_at"]):
        return False

    age = (local_now_dt() - latest["created_at"]).total_seconds()
    return str(entered_code).zfill(4) == str(latest["code"]).zfill(4) and age <= TOKEN_LIFETIME

def rep_live_code(session_id):
    latest = get_latest_code(session_id)
    if latest is None or pd.isna(latest["created_at"]):
        return write_new_code(session_id), TOKEN_LIFETIME

    age = (local_now_dt() - latest["created_at"]).total_seconds()
    if age >= TOKEN_LIFETIME:
        return write_new_code(session_id), TOKEN_LIFETIME
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

    st.markdown("### 📘 Attendance Details")
    st.write(f"**Department:** {session['department']}")
    st.write(f"**Course / Title:** {session['title']}")
    st.write(f"**Date:** {session['created_at'].split(' ')[0]}")
    st.divider()

    st.caption("📌 Naming format: Surname Firstname Middlename")
    name = st.text_input("Full Name")
    matric = st.text_input("Matric Number (11 digits)")

    if st.button("Submit Attendance"):
        if not re.fullmatch(r"\d{11}", str(matric).strip()):
            st.error("Invalid matric number.")
            return

        matric = str(matric).strip()

        records = load_csv(RECORDS_FILE, RECORD_COLS)

        # ✅ Duplicate check PER SESSION (case-insensitive for names)
        session_records = records[records["session_id"] == sid]

        if normalize(name) in session_records["name"].apply(normalize).values:
            st.error("Name already exists for this attendance.")
            return

        if matric in session_records["matric"].values:
            st.error("Matric already used for this attendance.")
            return

        # One entry per device per session
        if device_id() in session_records["device_id"].values:
            st.error("One entry per device.")
            return

        records.loc[len(records)] = [sid, name, matric, now(), device_id(), DEPARTMENT]
        save_csv(records, RECORDS_FILE)
        st.success("Attendance recorded.")

    st.divider()
    st.caption("💙 made with love EPE2025/26")

    return latest["code"], int(TOKEN_LIFETIME - age)
def rep_login():
    st.title("Course Rep Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        u_hash = sha256_hash(u)
        p_hash = sha256_hash(p)

        if u_hash == REP_USERNAME_HASH and p_hash == REP_PASSWORD_HASH:
            st.session_state.rep = True
            st.success("Login successful.")
            st.rerun()
        else:
            st.error("Invalid login credentials.")

def rep_dashboard():
    st_autorefresh(interval=1000, key="refresh")
    st.title(f"{DEPARTMENT} Course Rep Dashboard")

    sessions = load_csv(SESSIONS_FILE, SESSION_COLS)
    records = load_csv(RECORDS_FILE, RECORD_COLS)

    active_sessions = sessions[sessions["status"] == "Active"]

    if not active_sessions.empty:
        st.warning("⚠️ Attendance is ACTIVE. End it before starting a new one.")

    att_type = st.selectbox("Attendance Type", ["Daily", "Per Subject"])
    course = st.text_input("Course Code") if att_type == "Per Subject" else ""

    if st.button("Start Attendance"):
        if not active_sessions.empty:
            st.error("End current attendance first.")
        else:
            save_csv(pd.DataFrame(columns=RECORD_COLS), RECORDS_FILE)

            sid = str(time.time())
            title = session_title(att_type, course)

            sessions.loc[len(sessions)] = [
                sid, att_type, title, "Active", now(), DEPARTMENT
            ]
            save_csv(sessions, SESSIONS_FILE)

            write_new_code(sid)
            st.success("Attendance started — records cleared.")
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
    data = records[records["session_id"] == sid]

    st.divider()
    st.subheader(f"Session: {session['title']}")
    st.write(f"Department: {session['department']}")
    st.write(f"Status: {session['status']}")

    # ===== LIVE CODE =====
    if session["status"] == "Active":
        code, remaining = rep_live_code(sid)
        st.markdown(f"## Live Code: `{code}`")
        st.caption(f"Changes in {remaining} seconds")

        if st.button("🛑 END ATTENDANCE"):
            sessions.loc[sessions["session_id"] == sid, "status"] = "Ended"
            save_csv(sessions, SESSIONS_FILE)
            st.success("Attendance ended.")
            st.rerun()

    # ===== CSV DOWNLOAD (WITH S/N) =====
    if session["status"] == "Ended":
        safe_title = re.sub(r"[^\w\-]", "_", session["title"])
        filename = f"{DEPARTMENT}_{safe_title}_Attendance.csv"

        export_data = data.copy()
        export_data["department"] = session["department"]

        # Add S/N column
        export_data.insert(0, "S/N", range(1, len(export_data) + 1))

        csv_bytes = export_data[
            ["S/N", "department", "name", "matric", "time"]
        ].to_csv(index=False).encode()

        st.download_button(
            "📥 Download Attendance CSV",
            data=csv_bytes,
            file_name=filename,
            mime="text/csv"
        )

    st.divider()

    # ===== ADD STUDENT =====
    st.subheader("Add Student Manually")
    new_name = st.text_input("Student Name")
    new_matric = st.text_input("Matric Number")

    if st.button("Add Student"):
        if not new_name.strip():
            st.error("Enter student name.")
            return

        if not re.fullmatch(r"\d{11}", str(new_matric).strip()):
            st.error("Matric number must be 11 digits.")
            return

        new_matric = str(new_matric).strip()

        # Duplicate check PER SESSION
        session_records = records[records["session_id"] == sid]

        if normalize(new_name) in session_records["name"].apply(normalize).values:
            st.error("Name already exists for this attendance.")
            return

        if new_matric in session_records["matric"].values:
            st.error("Matric already used for this attendance.")
            return

        records.loc[len(records)] = [
            sid, new_name, new_matric, now(), "rep", DEPARTMENT
        ]
        save_csv(records, RECORDS_FILE)
        st.success("Student added.")
        st.rerun()

    # ===== EDIT STUDENT =====
    st.subheader("Edit Student Record")

    if not data.empty:
        selected = st.selectbox("Select Student", data["matric"])
        edit_name = st.text_input("Edit Name")
        edit_matric = st.text_input("Edit Matric")

        if st.button("Update Record"):
            if not edit_name.strip():
                st.error("Enter a valid name.")
                return

            if not re.fullmatch(r"\d{11}", str(edit_matric).strip()):
                st.error("Matric number must be 11 digits.")
                return

            edit_matric = str(edit_matric).strip()

            # Records for this session excluding the currently selected student
            session_records = records[records["session_id"] == sid]
            others = session_records[session_records["matric"] != selected]

            # Prevent duplicates after edit (case-insensitive name)
            if normalize(edit_name) in others["name"].apply(normalize).values:
                st.error("Another student already has this name in this attendance.")
                return

            if edit_matric in others["matric"].values:
                st.error("Another student already has this matric number in this attendance.")
                return

            records.loc[
                (records["session_id"] == sid) & (records["matric"] == selected),
                ["name", "matric"]
            ] = [edit_name, edit_matric]

            save_csv(records, RECORDS_FILE)
            st.success("Record updated.")
            st.rerun()

    # ===== DELETE STUDENT =====
    st.subheader("Delete Student")
    del_matric = st.text_input("Matric Number to Delete")

    if st.button("Delete Student"):
        records = records[
            ~((records["session_id"] == sid) & (records["matric"] == del_matric))
        ]
        save_csv(records, RECORDS_FILE)
        st.success("Student deleted.")
        st.rerun()

    # ===== VIEW TABLE (WITH S/N) =====
    st.subheader("Attendance Records")

    view_data = data.copy()
    view_data.insert(0, "S/N", range(1, len(view_data) + 1))

    st.dataframe(
        view_data[["S/N", "department", "name", "matric", "time"]],
        use_container_width=True
    )

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
