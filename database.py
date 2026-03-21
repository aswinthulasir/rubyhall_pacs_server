"""
database.py — SQLAlchemy engine, session factory, and Base declarative class.
Import `get_db` as a FastAPI dependency in every router that needs DB access.

Uses SQLite — no external database server required.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

# SQLite needs check_same_thread=False for FastAPI's threaded request handling
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

# Enable WAL mode and foreign key enforcement for SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()

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