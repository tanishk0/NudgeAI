"""Owner-scoped file storage, optimistic concurrency, and recovery checkpoints."""
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy.orm.attributes import set_committed_value
from app.db_models import (ProjectRecord, ProjectVersionRecord, WorkspaceSessionRecord,
    WorkspaceStateRecord, WorkspaceFileRecord, WorkspaceSnapshotRecord)
from app.file_policy import files_hash, validate_files
from app.models import Project, PublicProject, WorkspaceFile, WorkspaceSessionResponse
from app.seed import record_to_project

EXTENSION_LANGUAGE_MAP = {".py":"python", ".md":"markdown", ".json":"json", ".ts":"typescript", ".tsx":"typescript", ".js":"javascript", ".jsx":"javascript", ".sql":"sql", ".yml":"yaml", ".yaml":"yaml", ".html":"html", ".css":"css", ".sh":"shell", ".txt":"plaintext"}

def infer_language(path):
    return next((v for k,v in EXTENSION_LANGUAGE_MAP.items() if path.lower().endswith(k)), "plaintext")

def _starters(project):
    return [WorkspaceFile(**f.model_dump(), is_starter=True) for f in project.starter_files]

def _get_project_and_session(db, user_id, project_id):
    record = db.get(ProjectRecord, project_id)
    if not record:
        raise HTTPException(404, "Project not found.")
    session = db.query(WorkspaceSessionRecord).filter_by(user_id=user_id, project_id=project_id).first()
    if not session:
        from sqlalchemy.exc import IntegrityError
        project = record_to_project(record)
        try:
            with db.begin_nested():
                session = WorkspaceSessionRecord(user_id=user_id, project_id=project_id,
                    files=[f.model_dump() for f in _starters(project)],
                    active_file_path=project.tasks[0].target_file,
                    active_task_id=project.tasks[0].id, completed_task_ids=[], hint_levels={}, last_verification={})
                db.add(session)
                db.flush()
        except IntegrityError:
            session = db.query(WorkspaceSessionRecord).filter_by(user_id=user_id, project_id=project_id).one()
    session = db.query(WorkspaceSessionRecord).filter_by(id=session.id).populate_existing().with_for_update().one()
    state = db.query(WorkspaceStateRecord).filter_by(session_id=session.id).populate_existing().first()
    if not state:
        project = record_to_project(record)
        definition = project.model_dump(exclude={"version"})
        version_id = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
        from sqlalchemy.exc import IntegrityError
        try:
            with db.begin_nested():
                if not db.get(ProjectVersionRecord, version_id):
                    db.add(ProjectVersionRecord(id=version_id, project_id=project_id, definition=definition))
                    db.flush()
        except IntegrityError:
            pass
        state = WorkspaceStateRecord(session_id=session.id, version_id=version_id, revision=0)
        db.add(state)
        files = [WorkspaceFile(**raw) for raw in (session.files or [f.model_dump() for f in _starters(project)])]
        validate_files(files)
        for f in files:
            db.add(WorkspaceFileRecord(session_id=session.id, path=f.path, language=f.language, content=f.content, revision=0))
        db.flush()
    version = db.get(ProjectVersionRecord, state.version_id)
    project = Project(**version.definition, version=version.id)
    if project_id == "build-mini-swe-agent":
        project = _adopt_mini_swe_tasks(db, record, session, state, project)
    from app.project_briefs import refresh_learning_copy
    project = refresh_learning_copy(project)
    starters = {f.path:f for f in project.starter_files}
    rows = db.query(WorkspaceFileRecord).filter_by(session_id=session.id).order_by(WorkspaceFileRecord.path).all()
    files = [WorkspaceFile(path=r.path, language=r.language, content=r.content,
        is_starter=r.path in starters, read_only=starters[r.path].read_only if r.path in starters else False) for r in rows]
    set_committed_value(session, "files", [f.model_dump() for f in files])
    session._state = state
    return project, session


def _merge_course_scaffold(previous, scaffold):
    """Keep existing implementations while supplying newly introduced helpers."""
    import ast
    try:
        old, new = ast.parse(previous), ast.parse(scaffold)
    except SyntaxError:
        return previous
    def unfinished(node):
        return all(
            (isinstance(line, ast.Expr) and isinstance(line.value, ast.Constant) and isinstance(line.value.value, str)) or
            (isinstance(line, ast.Raise) and isinstance(line.exc, ast.Call) and isinstance(line.exc.func, ast.Name) and line.exc.func.id == 'NotImplementedError')
            for line in node.body)
    old_nodes = {getattr(node, 'name', None): node for node in old.body}
    for index, node in enumerate(new.body):
        saved = old_nodes.get(getattr(node, 'name', None))
        if isinstance(node, ast.FunctionDef) and isinstance(saved, ast.FunctionDef) and not unfinished(saved):
            new.body[index] = saved
        elif isinstance(node, ast.ClassDef) and isinstance(saved, ast.ClassDef):
            methods = {getattr(method, 'name', None): method for method in saved.body}
            for position, method in enumerate(node.body):
                original = methods.get(getattr(method, 'name', None))
                if isinstance(method, ast.FunctionDef) and isinstance(original, ast.FunctionDef) and not unfinished(original):
                    node.body[position] = original
    names = {getattr(node, 'name', None) for node in new.body}
    imports = [node for node in old.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    extras = [node for node in old.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name not in names]
    new.body = imports + new.body + extras
    return ast.unparse(new) + '\n'


def _adopt_mini_swe_tasks(db, record, session, state, project):
    """Adopt the current roadmap while retaining saved implementations.

    Old versions and an automatic checkpoint preserve previous course work.
    Completed tasks cannot be mapped from whole-module checks to individual
    function checks, so new task IDs require their own verification.
    """
    catalogue = record_to_project(record)
    wanted = [task.id for task in catalogue.tasks]
    if not wanted or not all(key.startswith("mini-swe-build-") for key in wanted):
        return project
    layout_change = catalogue.tasks[0].target_file.startswith('src/minisweagent/') and any(
        not task.target_file.startswith('src/minisweagent/') for task in project.tasks)
    if [task.id for task in project.tasks] == wanted and not layout_change:
        return project
    removing_setup = [task.id for task in project.tasks] == ['mini-swe-build-initialize', *wanted] and not layout_change
    rows = db.query(WorkspaceFileRecord).filter_by(session_id=session.id).all()
    previous_files = [dict(path=row.path, language=row.language, content=row.content,
                           read_only=False, is_starter=True) for row in rows]
    db.add(WorkspaceSnapshotRecord(session_id=session.id, revision=state.revision,
        label="Before mini-swe repository layout update" if layout_change else "Before individual-task course update", files=previous_files))
    definition = catalogue.model_dump(exclude={"version"})
    version_id = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    from sqlalchemy.exc import IntegrityError
    try:
        with db.begin_nested():
            if not db.get(ProjectVersionRecord, version_id):
                db.add(ProjectVersionRecord(id=version_id, project_id=project.id, definition=definition))
                db.flush()
    except IntegrityError:
        pass
    next_revision = state.revision + 1
    paths = {row.path for row in rows}
    if layout_change:
        from app.mini_swe_layout import migrate_workspace_sources
        contents = migrate_workspace_sources({row.path: row.content for row in rows}, catalogue, _merge_course_scaffold)
        starters = {file.path: file for file in catalogue.starter_files}
        old_rows = {row.path: row for row in rows}
        updated = [WorkspaceFile(path=path, content=content,
            language=starters[path].language if path in starters else old_rows[path].language)
            for path, content in contents.items()]
        validate_files(updated)
        for row in rows:
            if row.path not in contents:
                db.delete(row)
            else:
                row.content, row.revision = contents[row.path], next_revision
        for file in updated:
            if file.path not in old_rows:
                db.add(WorkspaceFileRecord(session_id=session.id, path=file.path, language=file.language,
                    content=file.content, revision=next_revision))
    for file in catalogue.starter_files:
        if removing_setup or layout_change:
            # Removing a lesson changes no source, so existing verification
            # hashes and progress remain valid.
            continue
        if file.path not in paths:
            db.add(WorkspaceFileRecord(session_id=session.id, path=file.path,
                language=file.language, content=file.content, revision=next_revision))
        elif file.path.endswith('.py') and not file.read_only:
            row = next(row for row in rows if row.path == file.path)
            row.content = _merge_course_scaffold(row.content, file.content)
            row.revision = next_revision
    if session.active_task_id not in wanted:
        session.active_task_id = catalogue.tasks[0].id
        session.active_file_path = catalogue.tasks[0].target_file
    elif layout_change:
        session.active_file_path = next(task.target_file for task in catalogue.tasks if task.id == session.active_task_id)
    session.completed_task_ids = [key for key in (session.completed_task_ids or []) if key in wanted]
    session.hint_levels = {key: value for key, value in (session.hint_levels or {}).items() if key in wanted}
    session.last_verification = {key: value for key, value in (session.last_verification or {}).items() if key in wanted}
    state.version_id = version_id
    state.revision = next_revision
    db.flush()
    return catalogue.model_copy(update={"version": version_id})

def unlocked_tasks(project, session):
    # A passed lesson remains accessible while the learner edits the next one.
    completed = set(session.completed_task_ids or [])
    result = []
    for task in sorted(project.tasks, key=lambda task: task.order):
        result.append(task.id)
        if task.id not in completed:
            break
    return result


def require_unlocked_task(project, session, task_id):
    if task_id not in {t.id for t in project.tasks}:
        raise HTTPException(404, 'Task not found.')
    if task_id not in unlocked_tasks(project, session):
        raise HTTPException(403, 'Complete the previous task to unlock this one.')


def _session_to_response(session, project):
    files = [WorkspaceFile(**f) for f in session.files]
    digest = files_hash(files)
    reports = {key: dict(value) for key, value in (session.last_verification or {}).items()}
    from app.verification_evidence import execution_failed, INCOMPLETE_FEEDBACK
    for report in reports.values():
        if execution_failed(report):
            report['execution_status'] = 'error'
            report['architectural_feedback'] = INCOMPLETE_FEEDBACK
    return WorkspaceSessionResponse(session_id=session.id, revision=session._state.revision, content_hash=digest,
        project=PublicProject(**project.model_dump()), files=files,
        active_file_path=session.active_file_path or files[0].path,
        active_task_id=session.active_task_id if session.active_task_id in unlocked_tasks(project, session) else unlocked_tasks(project, session)[-1],
        unlocked_task_ids=unlocked_tasks(project, session),
        completed_task_ids=[t for t in (session.completed_task_ids or []) if reports.get(t,{}).get("content_hash")==digest and reports[t].get("passed_all")],
        hint_levels=dict(session.hint_levels or {}), last_verification=reports,
        chat_messages=[dict(id=m.id, task_id=m.task_id, role=m.role, message_type=m.message_type,
            content=m.content, created_at=m.created_at.isoformat()) for m in session.chat_messages])

def _expect(session, revision):
    if session._state.revision != revision:
        raise HTTPException(409, "This workspace changed in another tab. Your local edits are preserved. Reload the saved version before retrying.")

def _write_files(db, session, files):
    try:
        validate_files(files)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    rows = {r.path:r for r in db.query(WorkspaceFileRecord).filter_by(session_id=session.id).all()}
    incoming = {f.path:f for f in files}
    revision = session._state.revision + 1
    for path,row in rows.items():
        if path not in incoming:
            db.delete(row)
    for path,f in incoming.items():
        row = rows.get(path)
        if row:
            if row.content != f.content or row.language != f.language:
                row.content, row.language, row.revision = f.content, f.language, revision
        else:
            db.add(WorkspaceFileRecord(session_id=session.id, path=path, language=f.language, content=f.content, revision=revision))
    session._state.revision = revision
    set_committed_value(session,"files",[f.model_dump() for f in files])

def _finish(db,session,project):
    db.flush()
    result = _session_to_response(session,project)
    db.commit()
    return result

def get_or_create_workspace_session(db,user_id,project_id):
    project,session = _get_project_and_session(db,user_id,project_id)
    return _finish(db,session,project)


def rebase_legacy_workspace_files(project, files):
    """Restore older drafts/checkpoints into the current package layout."""
    if project.id != 'build-mini-swe-agent' or not project.tasks[0].target_file.startswith('src/minisweagent/'):
        return files
    from app.mini_swe_layout import LEGACY_PATHS, migrate_workspace_sources
    if not any(file.path.startswith('phase_') and file.path in LEGACY_PATHS for file in files):
        return files
    previous = {file.path: file for file in files}
    starters = {file.path: file for file in project.starter_files}
    contents = migrate_workspace_sources({file.path: file.content for file in files}, project, _merge_course_scaffold)
    rebased = [WorkspaceFile(path=path, content=content,
        language=starters[path].language if path in starters else previous[path].language,
        is_starter=path in starters, read_only=starters[path].read_only if path in starters else False)
        for path, content in contents.items()]
    validate_files(rebased)
    return rebased

def update_workspace_state(db,user_id,project_id,req):
    project,session = _get_project_and_session(db,user_id,project_id)
    _expect(session,req.expected_revision)
    if req.active_task_id is not None:
        require_unlocked_task(project, session, req.active_task_id)
    if req.files is not None:
        rebased = rebase_legacy_workspace_files(project, req.files)
        if rebased is not req.files:
            req.files = rebased
            if req.active_file_path and req.active_file_path not in {file.path for file in rebased}:
                active = req.active_task_id or session.active_task_id
                req.active_file_path = next(task.target_file for task in project.tasks if task.id == active)
        starters = {f.path:f for f in project.starter_files}
        incoming = {f.path:f for f in req.files}
        current = {f["path"]:WorkspaceFile(**f) for f in session.files}
        for path,f in starters.items():
            incoming[path] = WorkspaceFile(**f.model_dump()) if f.read_only else incoming.get(path,current[path])
        files = [f.model_copy(update={"is_starter":f.path in starters,"read_only":starters[f.path].read_only if f.path in starters else False}) for f in incoming.values()]
        if files_hash(files) != files_hash(list(current.values())):
            _write_files(db,session,files)
    if req.active_file_path is not None:
        if req.active_file_path not in {f["path"] for f in session.files}:
            raise HTTPException(422,"Active file does not exist.")
        session.active_file_path = req.active_file_path
    if req.active_task_id is not None:
        if req.active_task_id not in {t.id for t in project.tasks}:
            raise HTTPException(422,"Task does not belong to this project.")
        session.active_task_id = req.active_task_id
    return _finish(db,session,project)

def create_user_file(db,user_id,project_id,req):
    project,session = _get_project_and_session(db,user_id,project_id)
    _expect(session,req.expected_revision)
    if req.path.casefold() in {f["path"].casefold() for f in session.files}:
        raise HTTPException(409,"A file with this path already exists.")
    files = [WorkspaceFile(**f) for f in session.files]+[WorkspaceFile(path=req.path,language=req.language or infer_language(req.path),content=req.content,is_starter=False)]
    _write_files(db,session,files)
    session.active_file_path = req.path
    return _finish(db,session,project)

def rename_user_file(db,user_id,project_id,req):
    project,session = _get_project_and_session(db,user_id,project_id)
    _expect(session,req.expected_revision)
    if req.old_path in {f.path for f in project.starter_files}:
        raise HTTPException(403,"Starter files cannot be renamed.")
    files = [WorkspaceFile(**f) for f in session.files]
    if req.old_path not in {f.path for f in files}:
        raise HTTPException(404,"File not found.")
    if req.new_path.casefold() in {f.path.casefold() for f in files}:
        raise HTTPException(409,"A file with this path already exists.")
    files = [f.model_copy(update={"path":req.new_path,"language":infer_language(req.new_path)}) if f.path==req.old_path else f for f in files]
    _write_files(db,session,files)
    if session.active_file_path==req.old_path:
        session.active_file_path=req.new_path
    return _finish(db,session,project)

def delete_user_file(db,user_id,project_id,file_path,expected_revision):
    project,session = _get_project_and_session(db,user_id,project_id)
    _expect(session,expected_revision)
    if file_path in {f.path for f in project.starter_files}:
        raise HTTPException(403,"Starter files cannot be deleted.")
    files=[WorkspaceFile(**f) for f in session.files]
    if file_path not in {f.path for f in files}:
        raise HTTPException(404,"File not found.")
    _write_files(db,session,[f for f in files if f.path!=file_path])
    if session.active_file_path==file_path:
        session.active_file_path=session.files[0]["path"]
    return _finish(db,session,project)

def checkpoint(db,session,label):
    item=WorkspaceSnapshotRecord(session_id=session.id,label=label[:160],revision=session._state.revision,files=list(session.files))
    db.add(item)
    db.flush()
    for old in db.query(WorkspaceSnapshotRecord).filter_by(session_id=session.id).order_by(WorkspaceSnapshotRecord.created_at.desc()).offset(20).all():
        db.delete(old)
    return item

def reset_workspace_session(db,user_id,project_id,req):
    project,session = _get_project_and_session(db,user_id,project_id)
    _expect(session,req.expected_revision)
    checkpoint(db,session,"Before reset")
    # An explicit restart adopts the current course; the checkpoint keeps the old files.
    project = record_to_project(db.get(ProjectRecord, project_id))
    definition = project.model_dump(exclude={'version'})
    version_id = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    if not db.get(ProjectVersionRecord, version_id):
        db.add(ProjectVersionRecord(id=version_id, project_id=project_id, definition=definition))
        db.flush()
    session._state.version_id = version_id
    project = project.model_copy(update={'version': version_id})
    _write_files(db,session,_starters(project))
    session.active_task_id = project.tasks[0].id
    session.active_file_path=project.tasks[0].target_file
    session.completed_task_ids,session.last_verification=[],{}
    if req.reset_progress:
        session.hint_levels={}
    return _finish(db,session,project)
