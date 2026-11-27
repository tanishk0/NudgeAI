from contextlib import asynccontextmanager
from typing import List
import asyncio
import io
import os
import re
import secrets
import time
import zipfile
import httpx
from fastapi import Request, Response
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
    PublicProject,
    RevisionRequest,
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
from app.workspace_service import _get_project_and_session, _expect, _write_files, _finish, checkpoint
from app.db_models import WorkspaceSnapshotRecord, WorkspaceRunRecord
from app.file_policy import files_hash
from app import runtime_service

_preview_tickets = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    project_count = init_db_and_seed()
    print(f"[Nudge DB] Database ready ({project_count} projects available).")
    yield
    await asyncio.to_thread(runtime_service.stop_all)
    _preview_tickets.clear()


app = FastAPI(
    title="Nudge API",
    description="Backend API for the Nudge AI-guided engineering learning platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    try:
        db_ok = await asyncio.to_thread(check_db_connection)
    except Exception:
        db_ok = False
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


@app.get('/api/me/project-progress')
async def project_progress(current_user: UserRecord = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.db_models import WorkspaceSessionRecord
    from app.workspace_service import _session_to_response
    result = {}
    sessions = db.query(WorkspaceSessionRecord).filter_by(user_id=current_user.id).all()
    for session in sessions:
        project, loaded = _get_project_and_session(db, current_user.id, session.project_id)
        state = _session_to_response(loaded, project)
        result[session.project_id] = bool(project.tasks) and all(t.id in state.completed_task_ids for t in project.tasks)
    return result


@app.get("/api/projects/{project_id}", response_model=PublicProject)
async def get_project(project_id: str, db: Session = Depends(get_db)):
    """Retrieve full details, starter files, and task breakdown for a specific project from PostgreSQL."""
    project = get_project_from_db(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return PublicProject(**project.model_dump())


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
    expected_revision: int = Query(..., ge=0),
    current_user: UserRecord = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user-created file from the workspace virtual file tree."""
    return delete_user_file(db, current_user.id, project_id, path, expected_revision)


@app.post("/api/workspace/{project_id}/reset", response_model=WorkspaceSessionResponse)
async def reset_workspace(
    project_id: str,
    payload: ResetWorkspaceRequest,
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


@app.post('/api/workspace/{project_id}/nudge/stream')
async def stream_nudge(project_id: str, payload: RequestNudgePayload, current_user=Depends(get_current_user)):
    from app.mentor_stream import mentor_stream
    return mentor_stream(request_progressive_nudge, current_user.id, project_id, payload)


@app.post('/api/workspace/{project_id}/chat/stream')
async def stream_chat(project_id: str, payload: SendChatPayload, current_user=Depends(get_current_user)):
    from app.mentor_stream import mentor_stream
    return mentor_stream(send_mentor_chat_message, current_user.id, project_id, payload)


@app.get("/api/workspace/{project_id}/snapshots")
def list_snapshots(project_id: str, current_user=Depends(get_current_user), db: Session=Depends(get_db)):
    _, session = _get_project_and_session(db, current_user.id, project_id)
    rows = db.query(WorkspaceSnapshotRecord).filter_by(session_id=session.id).order_by(WorkspaceSnapshotRecord.created_at.desc()).limit(20).all()
    result = [dict(id=r.id, label=r.label, revision=r.revision, created_at=r.created_at.isoformat()) for r in rows]
    db.commit()
    return result


@app.post("/api/workspace/{project_id}/snapshots")
def create_snapshot(project_id: str, payload: RevisionRequest, current_user=Depends(get_current_user), db: Session=Depends(get_db)):
    project, session = _get_project_and_session(db, current_user.id, project_id)
    _expect(session, payload.expected_revision)
    checkpoint(db, session, "Manual checkpoint")
    return _finish(db, session, project)


@app.post("/api/workspace/{project_id}/snapshots/{snapshot_id}/restore", response_model=WorkspaceSessionResponse)
def restore_snapshot(project_id: str, snapshot_id: str, payload: RevisionRequest, current_user=Depends(get_current_user), db: Session=Depends(get_db)):
    from app.models import WorkspaceFile
    project, session = _get_project_and_session(db, current_user.id, project_id)
    _expect(session, payload.expected_revision)
    snapshot = db.query(WorkspaceSnapshotRecord).filter_by(id=snapshot_id, session_id=session.id).first()
    if not snapshot:
        raise HTTPException(404, "Checkpoint not found.")
    from app.workspace_service import rebase_legacy_workspace_files
    saved_files = rebase_legacy_workspace_files(project, [WorkspaceFile(**f) for f in snapshot.files])
    checkpoint(db, session, "Before restore")
    _write_files(db, session, saved_files)
    if session.active_file_path not in {f.path for f in saved_files}:
        session.active_file_path = saved_files[0].path
    return _finish(db, session, project)


@app.get("/api/workspace/{project_id}/export")
def export_workspace(project_id: str, current_user=Depends(get_current_user), db: Session=Depends(get_db)):
    _, session = _get_project_and_session(db, current_user.id, project_id)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in session.files:
            archive.writestr(file["path"], file["content"])
    db.commit()
    return Response(stream.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{project_id}.zip"'})


@app.post("/api/workspace/{project_id}/run")
async def run_application(project_id: str, payload: RevisionRequest, current_user=Depends(get_current_user), db: Session=Depends(get_db)):
    project, session = _get_project_and_session(db, current_user.id, project_id)
    _expect(session, payload.expected_revision)
    response = _session_to_runtime(session)
    session_id, revision = session.id, session._state.revision
    db.commit()
    result = await asyncio.to_thread(runtime_service.run_project, project, session_id, revision, response)
    if result["status"] == "running":
        # Unpredictable, short-lived capability for iframe subrequests; no platform cookies forwarded.
        now = time.monotonic()
        for token, (sid, expiry) in list(_preview_tickets.items()):
            if sid == session_id or expiry < now:
                del _preview_tickets[token]
        ticket = secrets.token_urlsafe(32)
        _preview_tickets[ticket] = (session_id, now+600)
        result["preview_url"] = f'/api/previews/{ticket}' + result.pop("preview_path", "/")
    db.add(WorkspaceRunRecord(session_id=session_id, revision=revision, content_hash=files_hash(response), kind="run", result={k:v for k,v in result.items() if k != "preview_url"}))
    db.commit()
    return result


def _session_to_runtime(session):
    from app.models import WorkspaceFile
    return [WorkspaceFile(**f) for f in session.files]


@app.delete("/api/workspace/{project_id}/run")
async def stop_application(project_id: str, current_user=Depends(get_current_user), db: Session=Depends(get_db)):
    _, session = _get_project_and_session(db, current_user.id, project_id)
    session_id=session.id
    db.commit()
    await asyncio.to_thread(runtime_service.stop_project, session_id)
    for token,(sid,_) in list(_preview_tickets.items()):
        if sid==session_id:
            del _preview_tickets[token]
    return {"status":"stopped"}


@app.api_route("/api/previews/{ticket}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def preview_proxy(ticket: str, path: str, request: Request):
    entry = _preview_tickets.get(ticket)
    if not entry or entry[1] < time.monotonic():
        raise HTTPException(410,"Preview expired. Run the application again.")
    if request.method=="OPTIONS":
        return Response(headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Methods":"GET,POST,PUT,PATCH,DELETE,OPTIONS","Access-Control-Allow-Headers":"content-type"})
    body=await request.body()
    if len(body)>2*1024*1024:
        raise HTTPException(413,"Preview request is too large.")
    prefix=f"/api/previews/{ticket}/"
    path_with_query="/"+path+("?"+str(request.query_params) if request.query_params else "")
    result=await asyncio.to_thread(runtime_service.preview_response,entry[0],request.method,path_with_query,body,request.headers.get("content-type","application/octet-stream"))
    upstream={key.lower():value for key,value in result["headers"]}
    content_type=upstream.get("content-type","text/plain")
    headers={"Cache-Control":"no-store","Access-Control-Allow-Origin":"*",
        "Content-Security-Policy":"sandbox allow-scripts allow-forms; default-src 'none'; script-src 'unsafe-inline' http: https:; style-src 'unsafe-inline' http: https:; img-src data: http: https:; connect-src http: https:; form-action http: https:; base-uri http: https:"}
    if "location" in upstream:
        location=upstream["location"]
        headers["Location"]=prefix+location.lstrip("/") if location.startswith("/") and not location.startswith("//") else prefix
    data=result["body"]
    if "text/html" in content_type or "javascript" in content_type:
        html=data.decode("utf-8",errors="replace")
        html=re.sub(r"([\"'])/(?!/)",lambda match:match.group(1)+prefix,html)
        html=html.replace("<head>",f'<head><base href="{prefix}">',1)
        data=html.encode()
    return Response(data,status_code=result["status"],media_type=content_type,headers=headers)
