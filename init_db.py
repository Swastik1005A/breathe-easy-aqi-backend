from database import engine, Base
from models import Prediction, User

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()