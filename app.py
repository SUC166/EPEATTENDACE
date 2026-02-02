# app.py
import streamlit as st
import pandas as pd
import os
import re
import math
from datetime import datetime
import streamlit.components.v1 as components

ATTENDANCE_FILE = "attendance.csv"
COLUMNS = ["Full Name", "Matric No", "Time"]

# ===== GPS SETTINGS (LECTURE HALL COORDINATES) =====
# Provided coordinates for the lecture hall
LECTURE_LAT = 5.384071
LECTURE_LON = 6.999249
MAX_DISTANCE_METERS = 500


# ---------------- Utilities ----------------
def load_data():
    if os.path.exists(ATTENDANCE_FILE):
        try:
            return pd.read_csv(ATTENDANCE_FILE)
        except Exception:
            return pd.DataFrame(columns=COLUMNS)
    return pd.DataFrame(columns=COLUMNS)


def save_data(df):
    df.to_csv(ATTENDANCE_FILE, index=False)


def distance_m(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------- GPS HANDLING ----------------
if "gps" not in st.session_state:
    st.session_state.gps = None

components.html(
    """
    <script>
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                const url = new URL(window.location);
                url.searchParams.set('gps', `${lat},${lon}`);
                window.history.replaceState({}, '', url);
            }
        );
    }
    </script>
    """,
    height=0,
)

params = st.experimental_get_query_params()
if "gps" in params and st.session_state.gps is None:
    lat, lon = params["gps"][0].split(",")
    st.session_state.gps = (float(lat), float(lon))


# ---------------- Student Page ----------------
def attendance_page():
    st.title("EPE 100LVL Attendance")
    st.warning("📍 Location access is required to mark attendance")

    if st.session_state.gps is None:
        st.info("Waiting for GPS permission… Please allow location access.")
        st.stop()

    user_lat, user_lon = st.session_state.gps
    dist = distance_m(user_lat, user_lon, LECTURE_LAT, LECTURE_LON)

    if dist > MAX_DISTANCE_METERS:
        st.error("❌ You are not within 500 meters of the lecture hall")
        st.stop()

    st.success("✅ Location verified. You may mark attendance.")

    name = st.text_input("Full Name")
    matric = st.text_input("Matric / Reg Number (11 digits)")

    if st.button("Submit Attendance"):
        name_clean = name.strip()
        matric_clean = matric.strip()

        if not name_clean or not matric_clean:
            st.error("Please fill in all fields")
            return

        if not re.fullmatch(r"\d{11}", matric_clean):
            st.error("Matric number must be exactly 11 digits (numbers only)")
            return

        df = load_data()

        if name_clean.lower() in df["Full Name"].astype(str).str.lower().values:
            st.error("This name has already been recorded")
            return

        if matric_clean in df["Matric No"].astype(str).values:
            st.error("This matric number has already been recorded")
            return

        new_row = {
            "Full Name": name_clean,
            "Matric No": matric_clean,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_data(df)
        st.success("Attendance recorded successfully")

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

    edited_df = st.data_editor(df, num_rows="fixed", use_container_width=True)

    if st.button("Save Changes"):
        names_lower = edited_df["Full Name"].astype(str).str.strip().str.lower()
        matrics = edited_df["Matric No"].astype(str).str.strip()

        if names_lower.duplicated().any():
            st.error("Duplicate names detected.")
            return

        if matrics.duplicated().any():
            st.error("Duplicate matric numbers detected.")
            return

        if not matrics.apply(lambda x: bool(re.fullmatch(r"\d{11}", x))).all():
            st.error("All matric numbers must be exactly 11 digits.")
            return

        edited_df["Full Name"] = edited_df["Full Name"].astype(str).str.strip()
        edited_df["Matric No"] = matrics

        save_data(edited_df)
        st.success("Attendance updated successfully")

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
