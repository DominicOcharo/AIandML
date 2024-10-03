import cv2
from picamera2 import Picamera2
from ultralytics import YOLO
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from datetime import datetime
# from starlette.responses import StreamingResponse
import logging
# Video streaming generator function
from fastapi.responses import StreamingResponse

# Initialize the FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Picamera2
picam2 = Picamera2()
picam2.preview_configuration.main.size = (1280, 720)
picam2.preview_configuration.main.format = "RGB888"
picam2.preview_configuration.align()
picam2.configure("preview")
picam2.start()

# Load the YOLOv8 model
model = YOLO("best.pt")

# Define the necessary Pydantic models
class Detection(BaseModel):
    label: str
    confidence: float
    box: List[int]

class PredictionResult(BaseModel):
    detections: List[Detection]
    inference_time: float
    date: str
    time: str

class GpsData(BaseModel):
    latitude: float
    longitude: float
    altitude: float
    date: str
    time: str

# Variable to store the latest GPS data
latest_gps_data = None

@app.post("/gps", response_model=GpsData)
async def receive_gps_data(gps_data: GpsData):
    global latest_gps_data
    latest_gps_data = gps_data
    return gps_data

@app.get("/gps", response_model=GpsData)
async def get_gps_data():
    if latest_gps_data is None:
        raise HTTPException(status_code=404, detail="No GPS data available")

    # Directly return the GPS data with the already formatted date and time
    return GpsData(
        latitude=latest_gps_data.latitude,
        longitude=latest_gps_data.longitude,
        altitude=latest_gps_data.altitude,
        date=latest_gps_data.date,  # No conversion needed
        time=latest_gps_data.time   # No conversion needed
    )

def capture_and_predict() -> PredictionResult:
    # Capture frame-by-frame
    frame = picam2.capture_array()

    # Run YOLOv8 inference on the frame
    results = model(frame)

    # Extract detections and inference time
    detections = []
    for box in results[0].boxes:
        detections.append(Detection(
            label=results[0].names[int(box.cls[0])],  # Get the label using the class ID
            confidence=float(box.conf[0]),
            box=[int(coord) for coord in box.xyxy[0].tolist()]  # Convert to integers
        ))

    # Capture current date and time
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    return PredictionResult(
        detections=detections,
        inference_time=results[0].speed['inference'],
        date=date_str,
        time=time_str 
    )

@app.get("/predict", response_model=PredictionResult)
async def predict():
    return capture_and_predict()

# Video streaming generator function with proper MJPEG formatting
def video_stream():
    while True:
        frame = picam2.capture_array()

        # Run YOLOv8 inference on the frame
        results = model(frame)

        # Draw the bounding boxes on the frame
        for box in results[0].boxes:
            start_point = (int(box.xyxy[0][0]), int(box.xyxy[0][1]))
            end_point = (int(box.xyxy[0][2]), int(box.xyxy[0][3]))
            color = (0, 255, 0)
            thickness = 2
            cv2.rectangle(frame, start_point, end_point, color, thickness)

            # Add label and confidence
            label = results[0].names[int(box.cls[0])]
            confidence = f"{float(box.conf[0]) * 100:.2f}%"
            cv2.putText(frame, f"{label} {confidence}", (start_point[0], start_point[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Encode the frame in JPEG format
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        # Yield frame in byte format with proper MJPEG formatting
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')

# Video feed endpoint
@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(video_stream(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.on_event("shutdown")
def shutdown_event():
    picam2.close()

# To run the API: uvicorn mmm:app --host 192.168.100.8 --port 8000
