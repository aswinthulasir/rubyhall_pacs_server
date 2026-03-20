"""
database.py — SQLAlchemy engine, session factory, and Base declarative class.
Import `get_db` as a FastAPI dependency in every router that needs DB access.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

# Create the engine (pool_pre_ping helps recover from stale connections)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,        # recycle connections every hour
    echo=False,               # set True to log SQL queries during development
)

# Session factory — each request gets its own session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base shared by all models
Base = declarative_base()


# ─── FastAPI Dependency ─────────────────────────────────────────────────────────
def get_db():
    """
    Yields a database session for use in a single request,
    then closes it automatically when the request completes.
    Usage:
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()