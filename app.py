# app.py
import streamlit as st
import pandas as pd
import re
import requests
import math
from datetime import datetime
import streamlit.components.v1 as components

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
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ---------------- Student Attendance ----------------
def attendance_page():
    st.title("EPE 100LVL Attendance")
    st.info("📍 Tap **Verify Location** and allow the browser to share your location.")

    # Check GPS from query params
    params = st.query_params
    if "gps" in params and st.session_state.get("gps") is None:
        try:
            lat_str, lon_str = params["gps"][0].split(",")
            st.session_state.gps = (float(lat_str), float(lon_str))
        except Exception:
            st.session_state.gps = None

    # If GPS not yet obtained, show Verify button
    if "gps" not in st.session_state or st.session_state.gps is None:
        if st.button("📡 Verify Location"):
            components.html(
                """
                <script>
                if (!navigator.geolocation) {
                    alert('Geolocation is not supported by your browser.');
                } else {
                    navigator.geolocation.getCurrentPosition(
                        function(position) {
                            const lat = position.coords.latitude.toFixed(6);
                            const lon = position.coords.longitude.toFixed(6);
                            const url = new URL(window.location.href);
                            url.searchParams.set('gps', lat + ',' + lon);
                            url.searchParams.set('gps_ts', Date.now());
                            window.location.href = url.toString();
                        },
                        function(error) {
                            alert('Could not get location. Please allow location access.');
                        },
                        {enableHighAccuracy:true, timeout:10000}
                    );
                }
                </script>
                """,
                height=0,
            )
            st.stop()
        else:
            st.write("Click **Verify Location** to begin.")
            st.stop()

    # ---------------- At this point GPS exists ----------------
    lat, lon = st.session_state.gps
    st.success(f"Location detected: {lat:.6f}, {lon:.6f}")

    # Distance check
    dist = distance_m(lat, lon, LECTURE_LAT, LECTURE_LON)
    if dist > MAX_DISTANCE_METERS:
        st.error(f"❌ You are {int(dist)} m from the lecture hall. Attendance only allowed within {MAX_DISTANCE_METERS} m.")
        can_submit = False
    else:
        st.info(f"✅ You are {int(dist)} m from the lecture hall — you may submit attendance.")
        can_submit = True

    # ---------------- Student Inputs ----------------
    name = st.text_input("Full Name")
    matric = st.text_input("Matric / Reg Number (11 digits)")

    # Submit button only if in range
    if st.button("Submit Attendance") and can_submit:
        name_clean = name.strip()
        matric_clean = matric.strip()

        if not name_clean or not matric_clean:
            st.error("Please fill in all fields.")
            return

        if not re.fullmatch(r"\d{11}", matric_clean):
            st.error("Matric number must be exactly 11 digits.")
            return

        payload = {
            "full_name": name_clean,
            "matric_no": matric_clean,
            "latitude": lat,
            "longitude": lon,
        }

        try:
            res = requests.post(BACKEND_URL, json=payload, timeout=10)
            if res.status_code == 200:
                st.success("Attendance recorded successfully ✅")
            else:
                detail = None
                try:
                    detail = res.json().get("detail") or res.json().get("message")
                except Exception:
                    detail = res.text
                st.error(f"❌ {detail}")
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
    password = st.text_input("Password",
