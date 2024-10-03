import cv2
import asyncio
from picamera2 import Picamera2
from ultralytics import YOLO
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from databases import Database

# Database setup
DATABASE_URL = "mysql+asyncmy://root:1234@localhost/AIResults"

# SQLAlchemy models
Base = declarative_base()

class GpsDataModel(Base):
    __tablename__ = "gps_data"
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    date = Column(String(255))  # Stored as string in database
    time = Column(String(255))  # Stored as string in database

class PredictionResultModel(Base):
    __tablename__ = "prediction_results"
    id = Column(Integer, primary_key=True, index=True)
    detections = Column(JSON)
    inference_time = Column(Float)
    date = Column(String(255))  # Stored as string in database
    time = Column(String(255))  # Stored as string in database

# Initialize the database
engine = create_engine("mysql+pymysql://root:1234@localhost/AIResults")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables if they don't exist (synchronously)
def init_db():
    Base.metadata.create_all(bind=engine)

# Async database connection
database = Database(DATABASE_URL)

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

# Pydantic models
class Detection(BaseModel):
    label: str
    confidence: float
    box: List[int]

class PredictionResult(BaseModel):
    detections: List[Detection]
    inference_time: float
    date: str  # String format for Power Apps compatibility
    time: str  # String format for Power Apps compatibility

class GpsData(BaseModel):
    latitude: float
    longitude: float
    altitude: float
    date: int  # Timestamp (in seconds since epoch)
    time: int  # Timestamp (in seconds since epoch)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/gps", response_model=GpsData)
async def receive_gps_data(gps_data: GpsData, db: Session = Depends(get_db)):
    date_time = datetime.utcfromtimestamp(gps_data.date)
    date_str = date_time.strftime("%Y-%m-%d")
    time_str = date_time.strftime("%H:%M:%S")

    db_gps_data = GpsDataModel(
        latitude=gps_data.latitude,
        longitude=gps_data.longitude,
        altitude=gps_data.altitude,
        date=date_str,
        time=time_str
    )
    db.add(db_gps_data)
    db.commit()
    db.refresh(db_gps_data)
    return gps_data  # Return the input GPS data as is

@app.get("/gps", response_model=GpsData)
async def get_gps_data(db: Session = Depends(get_db)):
    gps_data = db.query(GpsDataModel).order_by(GpsDataModel.id.desc()).first()
    if not gps_data:
        raise HTTPException(status_code=404, detail="No GPS data available")
    
    # Convert date and time back to timestamps
    date_time = datetime.strptime(f"{gps_data.date} {gps_data.time}", "%Y-%m-%d %H:%M:%S")
    timestamp = int(date_time.timestamp())

    return GpsData(
        latitude=gps_data.latitude,
        longitude=gps_data.longitude,
        altitude=gps_data.altitude,
        date=timestamp,
        time=timestamp
    )

@app.get("/latest_gps_predictions", response_model=List[GpsData])
async def get_latest_gps_predictions(db: Session = Depends(get_db)):
    gps_data_list = db.query(GpsDataModel).order_by(GpsDataModel.id.desc()).limit(20).all()
    return [
        GpsData(
            latitude=gps_data.latitude,
            longitude=gps_data.longitude,
            altitude=gps_data.altitude,
            date=int(datetime.strptime(f"{gps_data.date} {gps_data.time}", "%Y-%m-%d %H:%M:%S").timestamp()),
            time=int(datetime.strptime(f"{gps_data.date} {gps_data.time}", "%Y-%m-%d %H:%M:%S").timestamp())
        )
        for gps_data in gps_data_list
    ]

@app.get("/all_gps_predictions", response_model=List[GpsData])
async def get_all_gps_predictions(db: Session = Depends(get_db)):
    gps_data_list = db.query(GpsDataModel).all()
    return [
        GpsData(
            latitude=gps_data.latitude,
            longitude=gps_data.longitude,
            altitude=gps_data.altitude,
            date=int(datetime.strptime(f"{gps_data.date} {gps_data.time}", "%Y-%m-%d %H:%M:%S").timestamp()),
            time=int(datetime.strptime(f"{gps_data.date} {gps_data.time}", "%Y-%m-%d %H:%M:%S").timestamp())
        )
        for gps_data in gps_data_list
    ]

@app.get("/latest_predictions", response_model=List[PredictionResult])
async def get_latest_predictions(db: Session = Depends(get_db)):
    predictions = db.query(PredictionResultModel).order_by(PredictionResultModel.id.desc()).limit(20).all()
    return [
        PredictionResult(
            detections=prediction.detections,
            inference_time=prediction.inference_time,
            date=str(int(datetime.strptime(f"{prediction.date} {prediction.time}", "%Y-%m-%d %H:%M:%S").timestamp())),
            time=str(int(datetime.strptime(f"{prediction.date} {prediction.time}", "%Y-%m-%d %H:%M:%S").timestamp()))
        )
        for prediction in predictions
    ]

@app.get("/all_predictions", response_model=List[PredictionResult])
async def get_all_predictions(db: Session = Depends(get_db)):
    predictions = db.query(PredictionResultModel).all()
    return [
        PredictionResult(
            detections=prediction.detections,
            inference_time=prediction.inference_time,
            date=str(int(datetime.strptime(f"{prediction.date} {prediction.time}", "%Y-%m-%d %H:%M:%S").timestamp())),
            time=str(int(datetime.strptime(f"{prediction.date} {prediction.time}", "%Y-%m-%d %H:%M:%S").timestamp()))
        )
        for prediction in predictions
    ]

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

    # Capture current date and time as timestamp
    now = datetime.now()
    timestamp = int(now.timestamp())

    return PredictionResult(
        detections=detections,
        inference_time=results[0].speed['inference'],
        date=str(timestamp),
        time=str(timestamp) 
    )

@app.get("/predict", response_model=PredictionResult)
async def predict(db: Session = Depends(get_db)):
    prediction = capture_and_predict()
    db_prediction = PredictionResultModel(
        detections=prediction.detections,
        inference_time=prediction.inference_time,
        date=datetime.utcfromtimestamp(int(prediction.date)).strftime("%Y-%m-%d"),
        time=datetime.utcfromtimestamp(int(prediction.time)).strftime("%H:%M:%S")
    )
    db.add(db_prediction)
    db.commit()
    db.refresh(db_prediction)
    return prediction

async def record_data_every_10_seconds():
    while True:
        # Fetch Prediction data
        prediction = capture_and_predict().dict()

        # Store prediction in the database
        query = PredictionResultModel.__table__.insert().values(
            detections=prediction['detections'],
            inference_time=prediction['inference_time'],
            date=datetime.utcfromtimestamp(int(prediction['date'])).strftime("%Y-%m-%d"),
            time=datetime.utcfromtimestamp(int(prediction['time'])).strftime("%H:%M:%S")
        )
        await database.execute(query)

        # Wait for 10 seconds before repeating
        await asyncio.sleep(20)

@app.get("/combined_predictions", response_model=dict)
async def combined_predictions():
    # Fetch GPS data
    gps_data = await get_gps_data()

    # Fetch Prediction data
    prediction = await predict()

    return {
        "gps_data": gps_data,
        "prediction": prediction
    }

@app.on_event("startup")
async def startup():
    init_db()
    await database.connect()
    asyncio.create_task(record_data_every_10_seconds())

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="192.168.100.8", port=8000)
