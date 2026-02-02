import streamlit as st
import pandas as pd
import os
import re
import hashlib
from datetime import datetime
import qrcode
import numpy as np
import cv2
from pyzbar.pyzbar import decode

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
        raw = f"{st.session_state}{datetime.now().date()}"
        st.session_state.device_id = hashlib.sha256(raw.encode()).hexdigest()
    return st.session_state.device_id

def generate_attendance_id(att_type, title):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H-%M")
    day = now.strftime("%A")

    if att_type == "Per Subject":
        return f"{date}_{title}_{time}"
    else:
        return f"{day}_{date}_{time}"

def generate_qr(attendance_id):
    img = qrcode.make(attendance_id)
    path = f"qr_{attendance_id}.png"
    img.save(path)
    return path

# ---------------- QR SCANNER ----------------
def scan_qr():
    st.subheader("Scan Attendance QR Code")
    img = st.camera_input("Point camera at QR code")

    if img:
        image = np.array(img)
        decoded = decode(image)

        if not decoded:
            st.error("No QR code detected. Try again.")
            return None

        return decoded[0].data.decode("utf-8")

    return None

# ---------------- STUDENT PAGE ----------------
def student_page():
    st.title("Student Attendance")

    qr_data = scan_qr()
    if not qr_data:
        st.info("Scan the QR code to continue.")
        return

    attendance_id = qr_data.strip()
    sessions = load_sessions()
    session = sessions[sessions["attendance_id"] == attendance_id]

    if session.empty:
        st.error("Invalid attendance QR.")
        return

    if session.iloc[0]["status"] != "Active":
        st.error("Attendance has been closed.")
        return

    st.success("Attendance validated")
    st.title(session.iloc[0]["title"])

    name = st.text_input("Full Name")
    matric = st.text_input("Matric Number (11 digits)")

    if st.button("Submit Attendance"):
        name = name.strip()
        matric = matric.strip()

        if not name or not matric:
            st.error("All fields required.")
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
            st.error("This matric number is already recorded.")
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

    st.subheader("Current Attendance")
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
        title = st.text_input("Course Code (e.g EPE101)")

    if st.button("Create Attendance"):
        if att_type == "Per Subject" and not title.strip():
            st.error("Course code required.")
            return

        attendance_id = generate_attendance_id(att_type, title)
        sessions = load_sessions()

        if attendance_id in sessions["attendance_id"].values:
            st.error("Attendance already exists.")
            return

        new = {
