from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import joblib, numpy as np, os
from models import Prediction, User
from schemas import AQIRequest, AQIResponse
from database import get_db, Base, engine

from auth_utils import hash_password, verify_password

# ---- INIT DB (CRITICAL) ----
Base.metadata.create_all(bind=engine)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title="AQI Prediction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://breathe-easy-aqi-frontend-sxk8.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- LOAD MODELS ----
model = joblib.load(os.path.join(BASE_DIR, "ml/aqi_model.pkl"))
state_encoder = joblib.load(os.path.join(BASE_DIR, "state_encoder.pkl"))
location_encoder = joblib.load(os.path.join(BASE_DIR, "location_encoder.pkl"))
type_encoder = joblib.load(os.path.join(BASE_DIR, "type_encoder.pkl"))

LOCATION_MAP = {"Delhi NCR": "Delhi"}
AREA_TYPE_MAP = {
    "Commercial": "Industrial Areas",
    "Industrial": "Industrial Areas",
    "Residential": "Residential, Rural and other Areas",
}

def safe_encode(enc, val):
    return int(enc.transform([val])[0]) if val in enc.classes_ else 0

def get_aqi_category(aqi):
    return (
        "Good" if aqi <= 50 else
        "Satisfactory" if aqi <= 100 else
        "Moderate" if aqi <= 200 else
        "Poor" if aqi <= 300 else
        "Very Poor" if aqi <= 400 else
        "Severe"
    )

# ---- PREDICT ----
@app.post("/predict", response_model=AQIResponse)
def predict(data: AQIRequest, db: Session = Depends(get_db)):
    try:
        X = np.array([[
            data.so2, data.no2, data.rspm,
            safe_encode(state_encoder, data.state),
            safe_encode(location_encoder, LOCATION_MAP.get(data.location, data.location)),
            safe_encode(type_encoder, AREA_TYPE_MAP.get(data.area_type, data.area_type)),
        ]])

        predicted = float(model.predict(X)[0])
        category = get_aqi_category(predicted)

        db.add(Prediction(
            state=data.state,
            location=data.location,
            area_type=data.area_type,
            so2=data.so2,
            no2=data.no2,
            rspm=data.rspm,
            predicted_aqi=predicted,
            category=category,
        ))
        db.commit()

        return {"predicted_aqi": predicted, "aqi_category": category}

    except Exception as e:
        print("PREDICT ERROR:", e)
        raise HTTPException(status_code=500, detail="Prediction failed")

# ---- DASHBOARD ----
@app.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    try:
        total = db.query(Prediction).count()
        if total == 0:
            return {
                "success": True,
                "data": {
                    "latestAQI": 0,
                    "category": "Unknown",
                    "healthRisk": "No data",
                    "lastUpdated": None,
                    "trend": 0,
                    "stats": {
                        "predictions": 0,
                        "citiesMonitored": 0,
                        "alertsIssued": 0,
                    },
                },
            }

        latest = db.query(Prediction).order_by(Prediction.created_at.desc()).first()
        avg = db.query(func.avg(Prediction.predicted_aqi)).scalar()

        return {
            "success": True,
            "data": {
                "latestAQI": round(latest.predicted_aqi, 2),
                "category": latest.category,
                "healthRisk": "Based on AQI",
                "lastUpdated": latest.created_at.isoformat(),
                "trend": 0,
                "stats": {
                    "predictions": total,
                    "citiesMonitored": db.query(Prediction.location).distinct().count(),
                    "alertsIssued": total,
                },
            },
        }

    except Exception as e:
        print("DASHBOARD ERROR:", e)
        raise HTTPException(status_code=500, detail="Dashboard failed")

# ---- HEALTH ----
@app.get("/health")
def health():
    return {"status": "ok"}

# ---------------- METADATA ----------------
@app.get("/metadata")
def metadata():
    return {
        "states": list(state_encoder.classes_),
        "locations": list(location_encoder.classes_),
        "area_types": list(type_encoder.classes_),
    }