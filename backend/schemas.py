from pydantic import BaseModel

class AQIRequest(BaseModel):
    state: str
    location: str
    area_type: str
    so2: float
    no2: float
    rspm: float


class AQIResponse(BaseModel):
    predicted_aqi: float
    aqi_category: str
