import requests
import streamlit as st
import re

def attendance_page():
    st.title("EPE 100LVL Attendance")
    st.info("📍 Allow location access to mark attendance")

    # Student info
    name = st.text_input("Full Name")
    matric = st.text_input("Matric / Reg Number (11 digits)")

    # Automatic GPS capture using browser
    st.markdown("""
    <script>
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(position) {
            const lat = position.coords.latitude.toFixed(6);
            const lon = position.coords.longitude.toFixed(6);
            document.getElementById('lat').value = lat;
            document.getElementById('lon').value = lon;
        });
    }
    </script>
    """, unsafe_allow_html=True)

    lat = st.number_input("Latitude", key="lat")
    lon = st.number_input("Longitude", key="lon")

    if st.button("Submit Attendance"):
        name_clean = name.strip()
        matric_clean = matric.strip()

        if not name_clean or not matric_clean or not lat or not lon:
            st.error("Please fill in all fields including GPS coordinates")
            return

        if not re.fullmatch(r"\d{11}", matric_clean):
            st.error("Matric number must be exactly 11 digits")
            return

        # Send to backend
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
