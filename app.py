# streamlit_app.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime

ATTENDANCE_FILE = "attendance.csv"

# ---------- Helpers ----------
def load_data():
    if os.path.exists(ATTENDANCE_FILE):
        return pd.read_csv(ATTENDANCE_FILE)
    return pd.DataFrame(columns=["Full Name", "Matric No", "Time"])


def save_data(df):
    df.to_csv(ATTENDANCE_FILE, index=False)


# ---------- Pages ----------
def attendance_page():
    st.title("EPE 100LVL Attendance")

    name = st.text_input("Full Name")
    matric = st.text_input("Matric / Reg Number")

    if st.button("Submit Attendance"):
        if name.strip() == "" or matric.strip() == "":
            st.error("Please fill in all fields")
            return

        df = load_data()

        # Prevent duplicate matric numbers
        if matric in df["Matric No"].values:
            st.warning("Attendance already recorded for this matric number")
            return

        new_row = {
            "Full Name": name,
            "Matric No": matric,
            "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_data(df)

        st.success("Attendance recorded successfully")

    st.subheader("Recorded Attendance")
    st.dataframe(load_data())



def rep_login_page():
    st.title("Course Rep Login")

    # Simple hardcoded login (can be improved later)
    USERNAME = "rep"
    PASSWORD = "epe100"

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == USERNAME and password == PASSWORD:
            st.session_state.logged_in = True
        else:
            st.error("Invalid login details")



def rep_dashboard():
    st.title("Course Rep Dashboard")

    df = load_data()
    st.subheader("Attendance List")
    st.dataframe(df)

    st.download_button(
        "Download CSV",
        data=df.to_csv(index=False),
        file_name="attendance.csv",
        mime="text/csv",
    )

    if st.button("Reset Attendance"):
        save_data(pd.DataFrame(columns=["Full Name", "Matric No", "Time"]))
        st.success("Attendance list has been reset")


# ---------- App Router ----------
def main():
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Go to", ["Attendance", "Course Rep"])

    if page == "Attendance":
        attendance_page()
    else:
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False

        if not st.session_state.logged_in:
            rep_login_page()
        else:
            rep_dashboard()


if __name__ == "__main__":
    main()
    
