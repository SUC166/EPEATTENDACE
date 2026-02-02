# app.py
import streamlit as st
import pandas as pd
import re
import requests
import math
from datetime import datetime
from streamlit_js_eval import streamlit_js_eval  # pip install streamlit-js-eval

# ---------------- Backend URL ----------------
BACKEND_URL = "https://epeattendace.onrender.com/submit"

# ---------------- Lecture Hall GPS ----------------
LECTURE_LAT = 5.384071
LECTURE_LON = 6.999249
MAX_DISTANCE_METERS = 500

# ---------------- Utilities ----------------
COLUMNS = ["Full Name", "Matric No", "Time"]

def load_data():
    try:
        return pd.read_csv("attendance.csv")
    except FileNotFoundError:
        return pd.DataFrame(columns=COLUMNS)

def save_data(df):
    df.to_csv("attendance.csv", index=False)

def distance_m(lat1, lon1, lat2, lon2):
    """Haversine distance in meters"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ---------------- Student Attendance ----------------
def attendance_page():
    st.title("EPE 100LVL Attendance")
    st.info("📍 Allow location access to mark attendance")

    name = st.text_input("Full Name")
    matric = st.text_input("Matric / Reg Number (11 digits)")

    # ---------------- GET GPS ----------------
    if "gps" not in st.session_state:
        try:
            gps = streamlit_js_eval(
                "navigator.geolocation.getCurrentPosition(pos => [pos.coords.latitude, pos.coords.longitude], err => null)",
                key="get_gps"
            )
            st.session_state.gps = gps
        except Exception as e:
            st.error(f"Error getting GPS: {e}")
            st.stop()

    if st.session_state.gps is None:
        st.warning("Waiting for GPS… Please allow location access on your device.")
        st.stop()

    lat, lon = st.session_state.gps
    st.success(f"Location detected: {lat:.6f}, {lon:.6f}")

    # ---------------- DISTANCE CHECK ----------------
    dist = distance_m(lat, lon, LECTURE_LAT, LECTURE_LON)
    if dist > MAX_DISTANCE_METERS:
        st.error(f"❌ You are {int(dist)} meters away from the lecture hall. Attendance can only be submitted within {MAX_DISTANCE_METERS} meters.")
        st.stop()
    else:
        st.info(f"✅ You are {int(dist)} meters from the lecture hall. You can submit attendance.")

    # ---------------- SUBMIT ATTENDANCE ----------------
    if st.button("Submit Attendance"):
        name_clean = name.strip()
        matric_clean = matric.strip()

        if not name_clean or not matric_clean:
            st.error("Please fill in all fields")
            return
        if not re.fullmatch(r"\d{11}", matric_clean):
            st.error("Matric number must be exactly 11 digits")
            return

        payload = {
            "full_name": name_clean,
            "matric_no": matric_clean,
            "latitude": lat,
            "longitude": lon
        }

        try:
            res = requests.post(BACKEND_URL, json=payload, timeout=10)
            if res.status_code == 200:
                st.success("Attendance recorded successfully ✅")
            else:
                st.error(f"❌ {res.json().get('detail', 'Unknown error')}")
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")

    st.subheader("Recorded Attendance")
    st.dataframe(load_data())

# ---------------- Course Rep Login ----------------
def rep_login_page():
    st.title("Course Rep Login")
    USERNAME = "rep"
    PASSWORD = "epe100"

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == USERNAME and password == PASSWORD:
            st.session_state.logged_in = True
        else:
            st.error("Invalid login details")

# ---------------- Course Rep Dashboard ----------------
def rep_dashboard():
    st.title("Course Rep Dashboard")

    df = load_data()
    if df.empty:
        st.info("No attendance recorded yet.")
        return

    st.subheader("Edit Attendance (Course Rep Only)")
    st.caption("You can correct names or matric numbers. All rules still apply.")

    edited_df = st.data_editor(df, num_rows="fixed", use_container_width=True)

    if st.button("Save Changes"):
        names_lower = edited_df["Full Name"].astype(str).str.strip().str.lower()
        matrics = edited_df["Matric No"].astype(str).str.strip()

        if names_lower.duplicated().any():
            st.error("Duplicate names detected (case-insensitive). Changes not saved.")
            return
        if matrics.duplicated().any():
            st.error("Duplicate matric numbers detected. Changes not saved.")
            return
        if not matrics.apply(lambda x: bool(re.fullmatch(r"\d{11}", x))).all():
            st.error("All matric numbers must be exactly 11 digits.")
            return

        edited_df["Full Name"] = edited_df["Full Name"].astype(str).str.strip()
        edited_df["Matric No"] = matrics

        save_data(edited_df)
        st.success("Attendance updated successfully")

    st.divider()

    st.download_button(
        "Download CSV",
        data=df.to_csv(index=False),
        file_name="attendance.csv",
        mime="text/csv",
    )

    if st.button("Reset Attendance"):
        save_data(pd.DataFrame(columns=COLUMNS))
        st.success("Attendance list has been reset")

# ---------------- App Router ----------------
def main():
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Go to", ["Attendance", "Course Rep"])

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if page == "Attendance":
        attendance_page()
    else:
        if not st.session_state.logged_in:
            rep_login_page()
        else:
            rep_dashboard()

if __name__ == "__main__":
    main()
