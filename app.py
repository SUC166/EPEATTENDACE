import streamlit as st
import re
import requests
import streamlit.components.v1 as components

# ---------------- Backend URL ----------------
BACKEND_URL = "https://epeattendace.onrender.com/submit"

# ---------------- Attendance Page ----------------
def attendance_page():
    st.title("EPE 100LVL Attendance")
    st.info("📍 Allow location access to mark attendance")

    # Student info
    name = st.text_input("Full Name")
    matric = st.text_input("Matric / Reg Number (11 digits)")

    # Initialize session_state for GPS
    if "lat" not in st.session_state:
        st.session_state.lat = None
    if "lon" not in st.session_state:
        st.session_state.lon = None

    # Inject JS to get GPS and update session_state
    components.html(
        """
        <script>
        function sendLocation(lat, lon){
            const streamlitEvent = new CustomEvent("streamlit:message", {detail: {lat: lat, lon: lon}});
            window.dispatchEvent(streamlitEvent);
        }

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function(position) {
                sendLocation(position.coords.latitude.toFixed(6), position.coords.longitude.toFixed(6));
            });
        }
        </script>
        """,
        height=0,
    )

    # Listen for JS messages and populate st.session_state
    js_code = """
    <script>
    window.addEventListener("message", (event) => {
        const data = event.data;
        if (data && data.type === "streamlit:setComponentValue") {
            console.log(data);
        }
    });
    </script>
    """
    components.html(js_code, height=0)

    # Display GPS status
    if st.session_state.lat is None or st.session_state.lon is None:
        st.warning("Waiting for GPS… Please allow location access on your device.")
        st.stop()
    else:
        st.success(f"Location detected: {st.session_state.lat}, {st.session_state.lon}")

    # Submit button
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
            "latitude": float(st.session_state.lat),
            "longitude": float(st.session_state.lon)
        }

        try:
            res = requests.post(BACKEND_URL, json=payload, timeout=10)
            if res.status_code == 200:
                st.success("Attendance recorded successfully ✅")
            else:
                st.error(f"❌ {res.json().get('detail', 'Unknown error')}")
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")
