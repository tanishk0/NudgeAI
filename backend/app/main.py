from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import Project, ProjectSummary
from app.projects_data import get_project_by_id, list_project_summaries

app = FastAPI(
    title="Nudge API",
    description="Backend API for the Nudge AI-guided engineering learning platform",
    version="0.1.0",
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
    return {"status": "ok", "service": "Nudge Backend"}


@app.get("/api/projects", response_model=List[ProjectSummary])
async def get_projects():
    """List all engineering projects available on Nudge."""
    return list_project_summaries()


@app.get("/api/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    """Retrieve full details, starter files, and task breakdown for a specific project."""
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project
