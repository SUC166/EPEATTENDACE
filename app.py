# =====================================
# ULASv4 — PART 1
# Core Imports, Config, Identity Layer
# =====================================

import streamlit as st
import pandas as pd
import numpy as np
import hashlib
import uuid
import secrets
import datetime
import pytz
import os

from streamlit_javascript import st_javascript
import extra_streamlit_components as stx

# =====================================
# APP CONFIG
# =====================================

st.set_page_config(
    page_title="ULASv4",
    layout="wide",
    initial_sidebar_state="expanded"
)

DATA_FILE = "attendance_records.csv"
COOKIE_NAME = "ulas_browser_id"
COOKIE_EXPIRY_DAYS = 90

cookie_manager = stx.CookieManager()

# =====================================
# COOKIE — BROWSER ID
# =====================================

def get_or_create_browser_id():
    cookies = cookie_manager.get_all()

    if COOKIE_NAME in cookies:
        return cookies[COOKIE_NAME]

    new_id = secrets.token_hex(16)
    expiry = datetime.datetime.utcnow() + datetime.timedelta(days=COOKIE_EXPIRY_DAYS)

    cookie_manager.set(
        COOKIE_NAME,
        new_id,
        expires_at=expiry
    )

    return new_id

browser_id = get_or_create_browser_id()

# =====================================
# JAVASCRIPT — DEVICE FINGERPRINT DATA
# =====================================

fingerprint_data = st_javascript("""
() => {
    return {
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        screenWidth: screen.width,
        screenHeight: screen.height,
        pixelRatio: window.devicePixelRatio || 1
    };
}
""")

if fingerprint_data is None:
    fingerprint_data = {
        "userAgent": "unknown",
        "platform": "unknown",
        "language": "unknown",
        "timezone": "unknown",
        "screenWidth": 0,
        "screenHeight": 0,
        "pixelRatio": 1
    }

def generate_fingerprint(data):
    raw = (
        str(data.get("userAgent")) +
        str(data.get("platform")) +
        str(data.get("language")) +
        str(data.get("timezone")) +
        str(data.get("screenWidth")) +
        str(data.get("screenHeight")) +
        str(data.get("pixelRatio"))
    )
    return hashlib.sha256(raw.encode()).hexdigest()

fingerprint_hash = generate_fingerprint(fingerprint_data)

# =====================================
# SESSION STATE CORE
# =====================================

if "browser_id" not in st.session_state:
    st.session_state.browser_id = browser_id

if "fingerprint" not in st.session_state:
    st.session_state.fingerprint = fingerprint_hash

if "risk_score" not in st.session_state:
    st.session_state.risk_score = 0


# =====================================
# ULASv4 — PART 2
# Storage + Schema + UUID Records
# =====================================

BASE_COLUMNS = [
    "record_id",
    "name",
    "matric",
    "course",
    "session_id",
    "timestamp",
    "browser_id",
    "fingerprint",
    "risk_score",
    "flagged"
]

def initialize_csv():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=BASE_COLUMNS)
        df.to_csv(DATA_FILE, index=False)

initialize_csv()

def load_records():
    return pd.read_csv(DATA_FILE)

def save_records(df):
    df.to_csv(DATA_FILE, index=False)


# =====================================
# ULASv4 — PART 3
# Proxy Risk Detection Engine
# =====================================

def calculate_risk_score(df, new_entry):
    score = 0

    # Same fingerprint marking multiple students
    same_fp = df[df["fingerprint"] == new_entry["fingerprint"]]
    if len(same_fp) >= 2:
        score += 30

    # Same browser marking multiple names
    same_browser = df[df["browser_id"] == new_entry["browser_id"]]
    if len(same_browser) >= 3:
        score += 25

    # Rapid submissions
    if not df.empty:
        try:
            last_time = pd.to_datetime(df.iloc[-1]["timestamp"])
            now = datetime.datetime.utcnow()
            if (now - last_time).total_seconds() < 10:
                score += 15
        except:
            pass

    flagged = score >= 40
    return score, flagged



# =====================================
# ULASv4 — PART 4
# Attendance Submission Engine
# =====================================

def normalize_text(text):
    return str(text).strip().lower()

def add_attendance(name, matric, course, session_id):
    df = load_records()

    norm_matric = normalize_text(matric)

    # Prevent duplicate matric per session
    duplicate = df[
        (df["session_id"] == session_id) &
        (df["matric"].str.lower() == norm_matric)
    ]

    if not duplicate.empty:
        return False, "Matric already recorded for this session."

    record_id = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat()

    new_entry = {
        "record_id": record_id,
        "name": name,
        "matric": matric,
        "course": course,
        "session_id": session_id,
        "timestamp": timestamp,
        "browser_id": st.session_state.browser_id,
        "fingerprint": st.session_state.fingerprint,
        "risk_score": 0,
        "flagged": False
    }

    risk, flagged = calculate_risk_score(df, new_entry)
    new_entry["risk_score"] = risk
    new_entry["flagged"] = flagged

    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
    save_records(df)

    return True, "Attendance recorded successfully."



# =====================================
# ULASv4 — PART 5
# Safe Edit & Delete Engine
# =====================================

def delete_record(record_id):
    df = load_records()
    df = df[df["record_id"] != record_id]
    save_records(df)

def edit_record(record_id, name, matric, course):
    df = load_records()

    df.loc[df["record_id"] == record_id, "name"] = name
    df.loc[df["record_id"] == record_id, "matric"] = matric
    df.loc[df["record_id"] == record_id, "course"] = course

    save_records(df)

# =====================================
# ULASv4 — PART 6
# Student Attendance Page
# =====================================

def student_page():
    st.title("ULASv4 — Student Attendance")

    session_id = st.text_input("Session Code")
    name = st.text_input("Full Name")
    matric = st.text_input("Matric Number")
    course = st.text_input("Course Code")

    if st.button("Submit Attendance"):
        if not session_id or not name or not matric or not course:
            st.error("Please fill all fields.")
        else:
            ok, msg = add_attendance(name, matric, course, session_id)
            if ok:
                st.success(msg)
            else:
                st.error(msg)


# =====================================
# ULASv4 — PART 7
# Admin Dashboard
# =====================================

def admin_dashboard():
    st.title("ULASv4 — Attendance Dashboard")

    df = load_records()

    if df.empty:
        st.info("No attendance records yet.")
        return

    st.subheader("📋 All Attendance Records")
    st.dataframe(df, use_container_width=True)

    flagged_df = df[df["flagged"] == True]

    if not flagged_df.empty:
        st.subheader("⚠️ Suspicious Entries")
        st.dataframe(flagged_df, use_container_width=True)

    st.subheader("🗑 Delete Record")
    del_id = st.text_input("Record ID to Delete")
    if st.button("Delete"):
        delete_record(del_id)
        st.success("Deleted. Refresh page.")

    st.subheader("✏️ Edit Record")
    edit_id = st.text_input("Record ID to Edit")
    new_name = st.text_input("New Name")
    new_matric = st.text_input("New Matric")
    new_course = st.text_input("New Course")

    if st.button("Update Record"):
        edit_record(edit_id, new_name, new_matric, new_course)
        st.success("Updated. Refresh page.")

# =====================================
# ULASv4 — PART 8
# Main App Router
# =====================================

def main():
    st.sidebar.title("ULASv4 Navigation")

    page = st.sidebar.radio(
        "Select Mode",
        ["Student Attendance", "Admin Dashboard"]
    )

    if page == "Student Attendance":
        student_page()

    elif page == "Admin Dashboard":
        admin_dashboard()

# =====================================
# ENTRY POINT
# =====================================

if __name__ == "__main__":
    main()

