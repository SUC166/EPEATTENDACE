
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import math
import csv
import os
import re

app = FastAPI()

ATTENDANCE_FILE = "attendance.csv"
LECTURE_LAT = 5.384071
LECTURE_LON = 6.999249
MAX_DISTANCE_METERS = 500
COLUMNS = ["Full Name", "Matric No", "Time"]

def distance_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def load_attendance():
    if not os.path.exists(ATTENDANCE_FILE):
        return []
    with open(ATTENDANCE_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def save_attendance(rows):
    with open(ATTENDANCE_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

class AttendanceRequest(BaseModel):
    full_name: str
    matric_no: str
    latitude: float
    longitude: float

@app.post("/submit")
def submit_attendance(data: AttendanceRequest):
    name = data.full_name.strip()
    matric = data.matric_no.strip()

    if not name or not matric:
        raise HTTPException(status_code=400, detail="Missing fields")
    if not re.fullmatch(r"\d{11}", matric):
        raise HTTPException(status_code=400, detail="Matric must be exactly 11 digits")

    dist = distance_m(data.latitude, data.longitude, LECTURE_LAT, LECTURE_LON)
    if dist > MAX_DISTANCE_METERS:
        raise HTTPException(status_code=403, detail="You are not within the lecture hall radius")

    rows = load_attendance()
    if any(r["Matric No"] == matric for r in rows):
        raise HTTPException(status_code=409, detail="Matric already recorded")
    if any(r["Full Name"].lower() == name.lower() for r in rows):
        raise HTTPException(status_code=409, detail="Name already recorded")

    rows.append({
        "Full Name": name,
        "Matric No": matric,
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_attendance(rows)
    return {"status": "success", "message": "Attendance recorded"}
