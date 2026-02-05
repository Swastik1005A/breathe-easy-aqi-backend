from sqlalchemy import Column, Integer, Float, String, DateTime
from database import Base
from datetime import datetime



class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)

    state = Column(String(100))
    location = Column(String(100))
    area_type = Column(String(100))

    so2 = Column(Float)
    no2 = Column(Float)
    rspm = Column(Float)

    predicted_aqi = Column(Float)
    category = Column(String(50))

    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)