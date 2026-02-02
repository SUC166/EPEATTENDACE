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

    # If gps query param present and not in session_state, capture it
    params = st.query_params
    if "gps" in params and st.session_state.get("gps") is None:
        try:
            lat_str, lon_str = params["gps"][0].split(",")
            st.session_state.gps = (float(lat_str), float(lon_str))
        except Exception:
            # malformed param -> ignore
            st.session_state.gps = None

    # If still no gps in session, show Verify button that triggers browser prompt
    if "gps" not in st.session_state or st.session_state.gps is None:
        if st.button("📡 Verify Location"):
            # This HTML/JS will ask for location and then reload page with gps query param.
            components.html(
                """
                <script>
                // Request geolocation, then redirect to same URL with gps query param
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
                            // navigate to the new URL (causes Streamlit to reload and pick up query params)
                            window.location.href = url.toString();
                        },
                        function(error) {
                            alert('Could not get location. Please allow location access and try again.');
                        },
                        {enableHighAccuracy: true, timeout:10000}
                    );
                }
                </script>
                """,
                height=0,
            )
            # stop so the component can run and browser can redirect
            st.stop()
        else:
            st.write("Click **Verify Location** to begin.")
            st.stop()

    # At this point we have GPS in st.session_state
    lat, lon = st.session_state.gps
    st.success(f"Location detected: {lat:.6f}, {lon:.6f}")

    # Distance check
    dist = distance_m(lat, lon, LECTURE_LAT, LECTURE_LON)
    if dist > MAX_DISTANCE_METERS:
        st.error(
            f"❌ You are {int(dist)} m from the lecture hall. Attendance allowed only within {MAX_DISTANCE_METERS} m."
        )
        st.stop()
    else:
        st.info(f"✅ You are {int(dist)} m from the lecture hall — you may submit attendance.")

    # Student inputs
    name = st.text_input("Full Name")
    matric = st.text_input("Matric / Reg Number (11 digits)")

    if st.button("Submit Attendance"):
        name_clean = name.strip()
        matric_clean = matric.strip()

        if not name_clean or not matric_clean:
            st.error("Please fill in all fields.")
            return

        if not re.fullmatch(r"\d{11}", matric_clean):
            st.error("Matric number must be exactly 11 digits.")
            return

        # Send to backend
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
                # backend return message under 'detail' or 'message'
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
    st.download_button("Download CSV", data=df.to_csv(index=False), file_name="attendance.csv", mime="text/csv")
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
