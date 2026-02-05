from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import joblib
import numpy as np

from schemas import AQIRequest, AQIResponse
from database import get_db
from models import Prediction
from fastapi import HTTPException
from sqlalchemy.orm import Session
from auth_utils import hash_password, verify_password
from models import User
from database import get_db

app = FastAPI(title="AQI Prediction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = joblib.load("ml/aqi_model.pkl")
state_encoder = joblib.load("state_encoder.pkl")
location_encoder = joblib.load("location_encoder.pkl")
type_encoder = joblib.load("type_encoder.pkl")

LOCATION_MAP = {
    "New Delhi": "Delhi",
    "East Delhi": "Delhi",
    "West Delhi": "Delhi",
    "North Delhi": "Delhi",
    "South Delhi": "Delhi",
    "Delhi NCR": "Delhi",
}

AREA_TYPE_MAP = {
    "Commercial": "Industrial Areas",
    "Commercial Area": "Industrial Areas",
    "Industrial": "Industrial Areas",
    "Residential": "Residential, Rural and other Areas",
    "Urban": "Residential, Rural and other Areas",
}

def normalize(value: str, mapping: dict) -> str:
    return mapping.get(value, value)

def safe_encode(encoder, value: str) -> int:
    if value in encoder.classes_:
        return int(encoder.transform([value])[0])
    if "unknown" in encoder.classes_:
        return int(encoder.transform(["unknown"])[0])
    return int(encoder.transform([encoder.classes_[0]])[0])

def get_aqi_category(aqi: float) -> str:
    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Satisfactory"
    elif aqi <= 200:
        return "Moderate"
    elif aqi <= 300:
        return "Poor"
    elif aqi <= 400:
        return "Very Poor"
    else:
        return "Severe"

@app.post("/predict", response_model=AQIResponse)
def predict_aqi(data: AQIRequest, db: Session = Depends(get_db)):
    state = normalize(data.state, {})
    location = normalize(data.location, LOCATION_MAP)
    area_type = normalize(data.area_type, AREA_TYPE_MAP)

    X = np.array([[
        data.so2,
        data.no2,
        data.rspm,
        safe_encode(state_encoder, state),
        safe_encode(location_encoder, location),
        safe_encode(type_encoder, area_type),
    ]])

    predicted_aqi = float(model.predict(X)[0])
    category = get_aqi_category(predicted_aqi)

    db.add(Prediction(
        state=state,
        location=location,
        area_type=area_type,
        so2=data.so2,
        no2=data.no2,
        rspm=data.rspm,
        predicted_aqi=predicted_aqi,
        category=category,
    ))
    db.commit()

    return {"predicted_aqi": predicted_aqi, "aqi_category": category}

@app.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    total_predictions = db.query(Prediction).count()
    cities_monitored = db.query(Prediction.location).distinct().count()

    latest = (
        db.query(Prediction)
        .order_by(Prediction.created_at.desc())
        .first()
    )

    now = datetime.utcnow()
    last_7 = now - timedelta(days=7)
    prev_14 = now - timedelta(days=14)

    current_avg = db.query(func.avg(Prediction.predicted_aqi)) \
        .filter(Prediction.created_at >= last_7).scalar()

    previous_avg = db.query(func.avg(Prediction.predicted_aqi)) \
        .filter(
            Prediction.created_at >= prev_14,
            Prediction.created_at < last_7
        ).scalar()

    trend = 0
    if current_avg and previous_avg and previous_avg != 0:
        trend = round(((previous_avg - current_avg) / previous_avg) * 100, 2)

    return {
        "success": True,
        "data": {
            "latestAQI": round(latest.predicted_aqi, 2) if latest else 0,
            "category": latest.category if latest else "Unknown",
            "healthRisk": "Based on latest AQI prediction",
            "lastUpdated": latest.created_at.isoformat() if latest else None,
            "trend": trend,
            "stats": {
                "predictions": total_predictions,
                "citiesMonitored": cities_monitored,
                "alertsIssued": total_predictions,
            },
        },
    }

# ---------------- METADATA ----------------
@app.get("/metadata")
def metadata():
    return {
        "states": list(state_encoder.classes_),
        "locations": list(location_encoder.classes_),
        "area_types": list(type_encoder.classes_),
    }


@app.post("/signup")
def signup(
    name: str,
    email: str,
    password: str,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": "User registered successfully"
    }



@app.post("/login")
def login(
    email: str,
    password: str,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "success": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }