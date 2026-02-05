import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def must_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing environment variable: {key}")
    return value

DATABASE_URL = (
    f"mysql+pymysql://{must_env('DB_USER')}:{must_env('DB_PASSWORD')}"
    f"@{must_env('DB_HOST')}:{must_env('DB_PORT')}/{must_env('DB_NAME')}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,
    connect_args={"ssl": {"ssl_mode": "REQUIRED"}},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()