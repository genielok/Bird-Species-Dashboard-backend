from fastapi import FastAPI, UploadFile, File, HTTPException

from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List
import os
import shutil
from datetime import datetime
from tinydb import TinyDB, Query
import uuid

from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer

app = FastAPI(title="BirdNET Analysis API")
db = TinyDB("db.json")

# 2. add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Load the BirdNET-Analyzer models ONCE when the app starts.
try:
    analyzer = Analyzer()
except Exception as e:
    analyzer = None
    print(f"FATAL: Could not load BirdNET Analyzer model. Error: {e}")


PROJECT_ID = 1234


@app.post("/analyze", summary="Analyze one or more audio files for bird detections")
async def handle_analysis(files: List[UploadFile] = File(...)) -> Dict:
    if not analyzer:
        raise HTTPException(
            status_code=500,
            detail="BirdNET Analyzer is not available. Check server logs.",
        )

    temp_dir = "temp_audio"
    os.makedirs(temp_dir, exist_ok=True)

    all_detections = []
    processed_filenames = []

    for file in files:
        processed_filenames.append(file.filename)
        temp_file_path = os.path.join(temp_dir, file.filename)
        try:
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            recording = Recording(
                analyzer=analyzer,
                path=temp_file_path,
                date=datetime.now(),
                min_conf=0.25,
            )
            recording.analyze()

            for det in recording.detections:
                detection_data = {
                    "id": str(uuid.uuid4()),
                    "scientific_name": det["scientific_name"],
                    "common_name": det["common_name"],
                    "start_time": det["start_time"],
                    "end_time": det["end_time"],
                    "date_time": recording.date.strftime("%Y-%m-%d"),
                    "geo_location": f"{getattr(recording, 'lat', '')}, {getattr(recording, 'lon', '')}",
                    "confidence": det["confidence"],
                    "filename": os.path.basename(file.filename),
                    "project_id": PROJECT_ID,
                    "model_version": analyzer.version,
                }
                all_detections.append(detection_data)

        except Exception as e:
            print(f"Error processing file {file.filename}: {e}")
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    # After processing all files, create a single database entry for this analysis session
    if processed_filenames:
        session_data = {
            "session_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "processed_files": processed_filenames,
            "total_detections": len(all_detections),
            "detections": all_detections,
        }
        db.insert(session_data)

    return {
        "code": 200,
        "message": f"Analysis successful for {len(files)} files.",
        "total": len(all_detections),
        "data": all_detections,
    }


@app.get("/detections", summary="Get all saved bird detections from the database")
def get_all_detections():
    """
    Retrieves all detection records stored in the database.
    """
    all_detections = db.all()
    # Sort by timestamp, newest first
    sorted_detections = sorted(
        all_detections, key=lambda x: x["timestamp"], reverse=True
    )
    return {
        "code": 200,
        "message": "Successfully retrieved all detections.",
        "data": sorted_detections,
    }


# Add a simple root endpoint to check if the server is running
@app.get("/")
def read_root():
    return {
        "message": "Welcome to the BirdNET Analysis API. Use the /analyze endpoint to process audio."
    }
