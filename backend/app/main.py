from contextlib import asynccontextmanager
from typing import List
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.ai_mentor import request_progressive_nudge, send_mentor_chat_message
from app.auth import get_current_user
from app.database import check_db_connection, get_db
from app.db_models import UserRecord
from app.models import (
    AuthenticatedUser,
    CreateFileRequest,
    Project,
    ProjectSummary,
    RenameFileRequest,
    RequestNudgePayload,
    ResetWorkspaceRequest,
    SendChatPayload,
    UpdateWorkspaceStateRequest,
    VerifyTaskRequest,
    WorkspaceSessionResponse,
)
from app.seed import get_project_from_db, init_db_and_seed, list_projects_from_db
from app.verifier import verify_workspace_task
from app.workspace_service import (
    create_user_file,
    delete_user_file,
    get_or_create_workspace_session,
    rename_user_file,
    reset_workspace_session,
    update_workspace_state,
)


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


@app.get("/api/workspace/{project_id}", response_model=WorkspaceSessionResponse)
async def load_workspace(
    project_id: str,
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Load or initialize the authenticated user's workspace session for a project."""
    return get_or_create_workspace_session(db, current_user.id, project_id)


@app.put("/api/workspace/{project_id}/state", response_model=WorkspaceSessionResponse)
async def save_workspace_state(
    project_id: str,
    payload: UpdateWorkspaceStateRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist file edits, active file tab, or active task selection in PostgreSQL."""
    return update_workspace_state(db, current_user.id, project_id, payload)


@app.post("/api/workspace/{project_id}/files", response_model=WorkspaceSessionResponse)
async def create_workspace_file(
    project_id: str,
    payload: CreateFileRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new user file in the workspace virtual file tree."""
    return create_user_file(db, current_user.id, project_id, payload)


@app.patch(
    "/api/workspace/{project_id}/files/rename", response_model=WorkspaceSessionResponse
)
async def rename_workspace_file(
    project_id: str,
    payload: RenameFileRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rename a user-created file in the workspace virtual file tree."""
    return rename_user_file(db, current_user.id, project_id, payload)


@app.delete("/api/workspace/{project_id}/files", response_model=WorkspaceSessionResponse)
async def remove_workspace_file(
    project_id: str,
    path: str = Query(..., description="Path of the user-created file to delete"),
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user-created file from the workspace virtual file tree."""
    return delete_user_file(db, current_user.id, project_id, path)


@app.post("/api/workspace/{project_id}/reset", response_model=WorkspaceSessionResponse)
async def reset_workspace(
    project_id: str,
    payload: ResetWorkspaceRequest = ResetWorkspaceRequest(),
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset workspace files back to starter template (and optionally reset task progress)."""
    return reset_workspace_session(db, current_user.id, project_id, payload)


@app.post("/api/workspace/{project_id}/verify", response_model=WorkspaceSessionResponse)
async def verify_task_solution(
    project_id: str,
    payload: VerifyTaskRequest,
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the Two-Layer Verification Engine (Python Sandbox + NVIDIA NIM Evaluator) for a task."""
    return await verify_workspace_task(db, current_user.id, project_id, payload)


@app.post("/api/workspace/{project_id}/nudge", response_model=WorkspaceSessionResponse)
async def trigger_progressive_nudge(
    project_id: str,
    payload: RequestNudgePayload,
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Advance the 4-step progressive hint state machine (Hint 1 -> Hint 2 -> Hint 3 -> Step 4 Solution)."""
    return await request_progressive_nudge(db, current_user.id, project_id, payload)


@app.post("/api/workspace/{project_id}/chat", response_model=WorkspaceSessionResponse)
async def send_chat_message(
    project_id: str,
    payload: SendChatPayload,
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a free-form developer question to the context-aware Nudge AI Mentor."""
    return await send_mentor_chat_message(db, current_user.id, project_id, payload)


