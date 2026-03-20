"""
create_db.py — One-time setup script.

Run this ONCE before starting the server:
    python create_db.py

What it does:
  1. Creates the MySQL database if it doesn't exist
  2. Creates all tables defined in models.py
  3. Seeds the roles table with the five default roles
  4. Creates a default admin account (admin / Admin@123)
"""

import sys
import pymysql
from sqlalchemy import text

# ── Step 0: ensure the database itself exists ──────────────────────────────────
def ensure_database_exists():
    """Create the MySQL database if it doesn't already exist."""
    conn = pymysql.connect(
        host     = "localhost",
        user     = "root",
        password = "Aswin2000",
        charset  = "utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `hospital_pacs` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        conn.commit()
        print("[OK] Database 'hospital_pacs' ready.")
    finally:
        conn.close()


# ── Step 1: create tables ──────────────────────────────────────────────────────
def create_tables():
    from database import engine, Base
    import models   # noqa: F401 — registers all ORM models with Base

    Base.metadata.create_all(bind=engine)
    print("[OK] All tables created.")


# ── Step 2: seed roles ─────────────────────────────────────────────────────────
def seed_roles():
    from database import SessionLocal
    from models import Role

    db = SessionLocal()
    try:
        default_roles = [
            Role(id=1, name="admin"),
            Role(id=2, name="doctor"),
            Role(id=3, name="lab_assistant"),
            Role(id=4, name="patient"),
            Role(id=5, name="radiologist"),
        ]
        for role in default_roles:
            exists = db.query(Role).filter(Role.id == role.id).first()
            if not exists:
                db.add(role)
        db.commit()
        print("[OK] Default roles seeded.")
    finally:
        db.close()


# ── Step 3: create default admin user ─────────────────────────────────────────
def seed_admin():
    from database import SessionLocal
    from models import User
    from auth.security import hash_password

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if existing:
            print("[SKIP] Admin user already exists.")
            return

        admin = User(
            username        = "admin",
            email           = "admin@hospital.local",
            full_name       = "System Administrator",
            hashed_password = hash_password("Admin@123"),
            role_id         = 1,
            is_active       = True,
        )
        db.add(admin)
        db.commit()
        print("[OK] Default admin created  →  username: admin  |  password: Admin@123")
        print("     *** Change this password immediately after first login! ***")
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  Hospital PACS — Database Setup")
    print("=" * 60)

    try:
        ensure_database_exists()
        create_tables()
        seed_roles()
        seed_admin()
        print("=" * 60)
        print("  Setup complete. You can now start the server:")
        print("  uvicorn main:app --reload")
        print("=" * 60)
    except Exception as exc:
        print(f"\n[ERROR] Setup failed: {exc}")
        sys.exit(1)