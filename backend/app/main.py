from contextlib import asynccontextmanager
from typing import List
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import check_db_connection, get_db
from app.db_models import UserRecord
from app.models import AuthenticatedUser, Project, ProjectSummary
from app.seed import get_project_from_db, init_db_and_seed, list_projects_from_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_count = init_db_and_seed()
    print(f"[Nudge DB] PostgreSQL connected & seeded ({project_count} projects ready).")
    yield


app = FastAPI(
    title="Nudge API",
    description="Backend API for the Nudge AI-guided engineering learning platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "Nudge Backend",
        "database": "connected" if db_ok else "disconnected",
    }


@app.get("/api/auth/me", response_model=AuthenticatedUser)
async def get_me(current_user: UserRecord = Depends(get_current_user)):
    """Return the currently authenticated Supabase user and sync their record in PostgreSQL."""
    return AuthenticatedUser(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        avatar_url=current_user.avatar_url,
    )


@app.get("/api/projects", response_model=List[ProjectSummary])
async def get_projects(db: Session = Depends(get_db)):
    """List all engineering projects available on Nudge from PostgreSQL."""
    return list_projects_from_db(db)


@app.get("/api/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, db: Session = Depends(get_db)):
    """Retrieve full details, starter files, and task breakdown for a specific project from PostgreSQL."""
    project = get_project_from_db(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project
