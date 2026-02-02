# app.py
import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime

ATTENDANCE_FILE = "attendance.csv"
COLUMNS = ["Full Name", "Matric No", "Time"]


def load_data():
    if os.path.exists(ATTENDANCE_FILE):
        try:
            return pd.read_csv(ATTENDANCE_FILE)
        except Exception:
            return pd.DataFrame(columns=COLUMNS)
    return pd.DataFrame(columns=COLUMNS)


def save_data(df):
    df.to_csv(ATTENDANCE_FILE, index=False)


# ---------------- Student Page ----------------
def attendance_page():
    st.title("EPE 100LVL Attendance")

    name = st.text_input("Full Name")
    matric = st.text_input("Matric / Reg Number (11 digits)")

    if st.button("Submit Attendance"):
        name_clean = name.strip()
        matric_clean = matric.strip()

        if not name_clean or not matric_clean:
            st.error("Please fill in all fields")
            return

        # Validate matric number: exactly 11 digits, no letters
        if not re.fullmatch(r"\d{11}", matric_clean):
            st.error("Matric number must be exactly 11 digits (numbers only)")
            return

        df = load_data()

        # Case-insensitive duplicate checks
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
    st.caption("You can correct names or matric numbers. All rules still apply.")

    edited_df = st.data_editor(
        df,
        num_rows="fixed",
        use_container_width=True,
    )

    if st.button("Save Changes"):
        # Validation after editing
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
    
