"""Opt-in loopback-only demo. Does not use the configured Supabase database."""
import os
from pathlib import Path

directory = Path(__file__).resolve().parent / ".demo"
directory.mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + (directory / "nudge.sqlite3").as_posix()
os.environ["FRONTEND_URL"] = "http://localhost:5174,http://127.0.0.1:5174"
from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal
from app.db_models import UserRecord


def demo_user():
    with SessionLocal() as db:
        user = db.get(UserRecord, "local-demo")
        if not user:
            user = UserRecord(id="local-demo", email="learner@demo.local", display_name="Demo learner")
            db.add(user)
            db.commit()
            db.refresh(user)
        db.expunge(user)
        return user


app.dependency_overrides[get_current_user] = demo_user

if __name__ == "__main__":
    import uvicorn
    print("Local demo: separate SQLite database, loopback only. Do not expose this server publicly.")
    uvicorn.run(app, host="127.0.0.1", port=8001)
