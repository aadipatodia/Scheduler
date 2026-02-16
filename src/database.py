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

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_TYPE = os.getenv("DATABASE_TYPE", "sqlite")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/scheduler.db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "ai_scheduler")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


def get_database_url() -> str:
    """
    Get database URL based on configuration
    """
    if DATABASE_TYPE == "postgresql":
        return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    else:
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
        return f"sqlite:///{SQLITE_DB_PATH}"


# Create engine
DATABASE_URL = get_database_url()

if DATABASE_TYPE == "sqlite":
    # SQLite specific configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL query logging
    )
else:
    # PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=False
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