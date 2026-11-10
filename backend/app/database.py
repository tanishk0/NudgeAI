import os
from pathlib import Path
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Load backend/.env reliably regardless of working directory
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def get_database_url() -> str:
    raw_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("DATABASE_URl")
        or ""
    ).strip().strip('"').strip("'")

    if not raw_url:
        raise RuntimeError(
            "DATABASE_URL is not set in backend/.env. Please provide a PostgreSQL connection URI."
        )

    # Normalize standard postgres:// or postgresql:// URI to SQLAlchemy psycopg v3 driver
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql+psycopg://" + raw_url[len("postgres://") :]
    elif raw_url.startswith("postgresql://"):
        raw_url = "postgresql+psycopg://" + raw_url[len("postgresql://") :]

    return raw_url


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Verify PostgreSQL connectivity with a lightweight SELECT 1."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True

