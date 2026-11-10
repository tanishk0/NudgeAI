from typing import Dict, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db_models import ChatMessageRecord, ProjectRecord, WorkspaceSessionRecord
from app.models import (
    ChatMessageItem,
    CreateFileRequest,
    Project,
    RenameFileRequest,
    ResetWorkspaceRequest,
    UpdateWorkspaceStateRequest,
    WorkspaceFile,
    WorkspaceSessionResponse,
)
from app.seed import record_to_project

EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".py": "python",
    ".md": "markdown",
    ".json": "json",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".sql": "sql",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".html": "html",
    ".css": "css",
    ".sh": "shell",
    ".txt": "plaintext",
}


def infer_language(file_path: str) -> str:
    lower = file_path.lower().strip()
    for ext, lang in EXTENSION_LANGUAGE_MAP.items():
        if lower.endswith(ext):
            return lang
    return "python"


def _build_starter_workspace_files(project: Project) -> List[Dict]:
    return [
        WorkspaceFile(
            path=f.path,
            language=f.language or infer_language(f.path),
            content=f.content,
            read_only=f.read_only,
            is_starter=True,
        ).model_dump()
        for f in project.starter_files
    ]


def _default_active_file(project: Project) -> str:
    for f in project.starter_files:
        if not f.read_only:
            return f.path
    return project.starter_files[0].path if project.starter_files else ""


def _build_welcome_message(project: Project) -> str:
    first_task = project.tasks[0] if project.tasks else None
    task_line = (
        f"\n\n**Active Task 1 — {first_task.title}**:\n{first_task.objective}"
        if first_task
        else ""
    )
    return (
        f"Welcome to **{project.title}**.\n\n"
        f"**Why the AI Failed:** {project.ai_failure_mode}"
        f"{task_line}\n\n"
        "Inspect the code in the editor. You can ask me conceptual questions anytime, "
        "or click **Get Nudge (1/3)** when you want a targeted hint based on your live code."
    )


def _session_to_response(
    session: WorkspaceSessionRecord, project: Project
) -> WorkspaceSessionResponse:
    starter_paths = {f.path: f for f in project.starter_files}
    normalized_files: List[WorkspaceFile] = []

    for raw in session.files or []:
        path = raw.get("path", "")
        is_starter = path in starter_paths
        read_only = starter_paths[path].read_only if is_starter else bool(raw.get("read_only", False))
        normalized_files.append(
            WorkspaceFile(
                path=path,
                language=raw.get("language") or infer_language(path),
                content=raw.get("content", ""),
                read_only=read_only,
                is_starter=is_starter,
            )
        )

    messages: List[ChatMessageItem] = [
        ChatMessageItem(
            id=m.id,
            task_id=m.task_id,
            role=m.role,  # type: ignore[arg-type]
            message_type=m.message_type,  # type: ignore[arg-type]
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in (session.chat_messages or [])
    ]

    default_task_id = project.tasks[0].id if project.tasks else ""
    default_file_path = _default_active_file(project)

    return WorkspaceSessionResponse(
        session_id=session.id,
        project=project,
        files=normalized_files,
        active_file_path=session.active_file_path or default_file_path,
        active_task_id=session.active_task_id or default_task_id,
        completed_task_ids=list(session.completed_task_ids or []),
        hint_levels=dict(session.hint_levels or {}),
        last_verification=dict(session.last_verification or {}),
        chat_messages=messages,
    )


def _get_project_and_session(
    db: Session, user_id: str, project_id: str
) -> tuple[Project, WorkspaceSessionRecord]:
    project_record = (
        db.query(ProjectRecord).filter(ProjectRecord.id == project_id).first()
    )
    if not project_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )

    project = record_to_project(project_record)

    session = (
        db.query(WorkspaceSessionRecord)
        .filter(
            WorkspaceSessionRecord.user_id == user_id,
            WorkspaceSessionRecord.project_id == project_id,
        )
        .first()
    )

    if not session:
        first_task_id = project.tasks[0].id if project.tasks else ""
        initial_hints = {t.id: 0 for t in project.tasks}

        session = WorkspaceSessionRecord(
            user_id=user_id,
            project_id=project_id,
            files=_build_starter_workspace_files(project),
            active_file_path=_default_active_file(project),
            active_task_id=first_task_id,
            completed_task_ids=[],
            hint_levels=initial_hints,
            last_verification={},
        )
        db.add(session)
        db.flush()

        welcome_msg = ChatMessageRecord(
            session_id=session.id,
            task_id=first_task_id,
            role="assistant",
            message_type="chat",
            content=_build_welcome_message(project),
        )
        db.add(welcome_msg)
        db.commit()
        db.refresh(session)

    return project, session


def get_or_create_workspace_session(
    db: Session, user_id: str, project_id: str
) -> WorkspaceSessionResponse:
    project, session = _get_project_and_session(db, user_id, project_id)
    return _session_to_response(session, project)


def update_workspace_state(
    db: Session,
    user_id: str,
    project_id: str,
    req: UpdateWorkspaceStateRequest,
) -> WorkspaceSessionResponse:
    project, session = _get_project_and_session(db, user_id, project_id)
    starter_map = {f.path: f for f in project.starter_files}

    if req.files is not None:
        incoming_map = {f.path: f for f in req.files}
        merged_files: List[Dict] = []

        # 1. Always preserve starter files (protecting read_only starter files from mutation)
        for starter in project.starter_files:
            if starter.read_only:
                merged_files.append(
                    WorkspaceFile(
                        path=starter.path,
                        language=starter.language,
                        content=starter.content,
                        read_only=True,
                        is_starter=True,
                    ).model_dump()
                )
            elif starter.path in incoming_map:
                inc = incoming_map[starter.path]
                merged_files.append(
                    WorkspaceFile(
                        path=starter.path,
                        language=starter.language,
                        content=inc.content,
                        read_only=False,
                        is_starter=True,
                    ).model_dump()
                )
            else:
                # Keep existing starter file content from session if omitted
                existing_starter = next(
                    (f for f in (session.files or []) if f.get("path") == starter.path),
                    None,
                )
                merged_files.append(
                    existing_starter
                    or WorkspaceFile(
                        path=starter.path,
                        language=starter.language,
                        content=starter.content,
                        read_only=starter.read_only,
                        is_starter=True,
                    ).model_dump()
                )

        # 2. Include user-created files
        for inc in req.files:
            if inc.path not in starter_map:
                merged_files.append(
                    WorkspaceFile(
                        path=inc.path.strip(),
                        language=inc.language or infer_language(inc.path),
                        content=inc.content,
                        read_only=False,
                        is_starter=False,
                    ).model_dump()
                )

        session.files = merged_files
        flag_modified(session, "files")

    if req.active_file_path is not None:
        session.active_file_path = req.active_file_path

    if req.active_task_id is not None:
        valid_task_ids = {t.id for t in project.tasks}
        if req.active_task_id in valid_task_ids:
            session.active_task_id = req.active_task_id

    db.commit()
    db.refresh(session)
    return _session_to_response(session, project)


def create_user_file(
    db: Session, user_id: str, project_id: str, req: CreateFileRequest
) -> WorkspaceSessionResponse:
    project, session = _get_project_and_session(db, user_id, project_id)
    clean_path = req.path.strip().lstrip("/")
    if not clean_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File path cannot be empty.",
        )

    existing_paths = {f.get("path") for f in (session.files or [])}
    if clean_path in existing_paths:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File '{clean_path}' already exists in this workspace.",
        )

    new_file = WorkspaceFile(
        path=clean_path,
        language=req.language or infer_language(clean_path),
        content=req.content,
        read_only=False,
        is_starter=False,
    ).model_dump()

    updated_files = list(session.files or []) + [new_file]
    session.files = updated_files
    session.active_file_path = clean_path
    flag_modified(session, "files")

    db.commit()
    db.refresh(session)
    return _session_to_response(session, project)


def rename_user_file(
    db: Session, user_id: str, project_id: str, req: RenameFileRequest
) -> WorkspaceSessionResponse:
    project, session = _get_project_and_session(db, user_id, project_id)
    old_path = req.old_path.strip()
    new_path = req.new_path.strip().lstrip("/")

    if not new_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New file path cannot be empty.",
        )

    starter_paths = {f.path for f in project.starter_files}
    if old_path in starter_paths:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Starter project files cannot be renamed.",
        )

    files_list = list(session.files or [])
    if any(f.get("path") == new_path for f in files_list):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A file named '{new_path}' already exists.",
        )

    found = False
    for f in files_list:
        if f.get("path") == old_path:
            f["path"] = new_path
            f["language"] = infer_language(new_path)
            found = True
            break

    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{old_path}' not found.",
        )

    session.files = files_list
    if session.active_file_path == old_path:
        session.active_file_path = new_path
    flag_modified(session, "files")

    db.commit()
    db.refresh(session)
    return _session_to_response(session, project)


def delete_user_file(
    db: Session, user_id: str, project_id: str, file_path: str
) -> WorkspaceSessionResponse:
    project, session = _get_project_and_session(db, user_id, project_id)
    target = file_path.strip()

    starter_paths = {f.path for f in project.starter_files}
    if target in starter_paths:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Starter project files cannot be deleted.",
        )

    files_list = list(session.files or [])
    remaining = [f for f in files_list if f.get("path") != target]
    if len(remaining) == len(files_list):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{target}' not found.",
        )

    session.files = remaining
    if session.active_file_path == target:
        session.active_file_path = _default_active_file(project)
    flag_modified(session, "files")

    db.commit()
    db.refresh(session)
    return _session_to_response(session, project)


def reset_workspace_session(
    db: Session, user_id: str, project_id: str, req: ResetWorkspaceRequest
) -> WorkspaceSessionResponse:
    project, session = _get_project_and_session(db, user_id, project_id)
    session.files = _build_starter_workspace_files(project)
    session.active_file_path = _default_active_file(project)
    flag_modified(session, "files")

    if req.reset_progress:
        first_task_id = project.tasks[0].id if project.tasks else ""
        session.active_task_id = first_task_id
        session.completed_task_ids = []
        session.hint_levels = {t.id: 0 for t in project.tasks}
        session.last_verification = {}
        flag_modified(session, "completed_task_ids")
        flag_modified(session, "hint_levels")
        flag_modified(session, "last_verification")

        db.query(ChatMessageRecord).filter(
            ChatMessageRecord.session_id == session.id
        ).delete()
        db.add(
            ChatMessageRecord(
                session_id=session.id,
                task_id=first_task_id,
                role="assistant",
                message_type="chat",
                content=_build_welcome_message(project),
            )
        )

    db.commit()
    db.refresh(session)
    return _session_to_response(session, project)

