"""
Database configuration and connection management
"""
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv
from .models import Base

load_dotenv()

DATABASE_TYPE = os.getenv("DATABASE_TYPE", "sqlite")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/scheduler.db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ai_scheduler")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


def get_database_url() -> str:
    # Render (and other PaaS) provide DATABASE_URL directly
    direct_url = os.getenv("DATABASE_URL")
    if direct_url:
        # Render uses "postgres://..." but SQLAlchemy 2.x requires "postgresql://..."
        if direct_url.startswith("postgres://"):
            direct_url = direct_url.replace("postgres://", "postgresql://", 1)
        return direct_url

    if DATABASE_TYPE == "postgresql":
        return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    else:
        os.makedirs(os.path.dirname(SQLITE_DB_PATH) or ".", exist_ok=True)
        return f"sqlite:///{SQLITE_DB_PATH}"


DATABASE_URL = get_database_url()

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=False,
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Initialize database - create all tables
    """
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized successfully at: {DATABASE_URL}")


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session in FastAPI endpoints
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_db():
    """
    Drop all tables and recreate them (USE WITH CAUTION!)
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Database reset successfully")


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()