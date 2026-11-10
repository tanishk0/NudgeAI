from typing import List, Optional
from sqlalchemy.orm import Session

from app.database import Base, engine, SessionLocal
from app.db_models import ProjectRecord
from app.models import Project, ProjectSummary, ProjectFile, TaskItem
from app.projects_data import PROJECTS_DATA


def record_to_project(record: ProjectRecord) -> Project:
    """Convert a PostgreSQL ProjectRecord row into a Pydantic Project model."""
    return Project(
        id=record.id,
        title=record.title,
        subtitle=record.subtitle,
        difficulty=record.difficulty,  # type: ignore[arg-type]
        category=record.category,
        tags=list(record.tags or []),
        estimated_minutes=record.estimated_minutes,
        problem_statement=record.problem_statement,
        system_context=record.system_context,
        ai_failure_mode=record.ai_failure_mode,
        starter_files=[ProjectFile(**f) for f in (record.starter_files or [])],
        tasks=[TaskItem(**t) for t in (record.tasks or [])],
    )


def record_to_summary(record: ProjectRecord) -> ProjectSummary:
    """Convert a PostgreSQL ProjectRecord row into a lightweight ProjectSummary model."""
    return ProjectSummary(
        id=record.id,
        title=record.title,
        subtitle=record.subtitle,
        difficulty=record.difficulty,  # type: ignore[arg-type]
        category=record.category,
        tags=list(record.tags or []),
        estimated_minutes=record.estimated_minutes,
        ai_failure_mode=record.ai_failure_mode,
        task_count=len(record.tasks or []),
    )


def init_db_and_seed() -> int:
    """
    Create PostgreSQL tables if they do not exist and upsert starter projects
    from `PROJECTS_DATA` so the database is always ready.
    Returns the number of projects in the database.
    """
    # Ensure all models are imported before create_all
    import app.db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        for p in PROJECTS_DATA:
            existing = db.query(ProjectRecord).filter(ProjectRecord.id == p.id).first()
            starter_files_json = [f.model_dump() for f in p.starter_files]
            tasks_json = [t.model_dump() for t in p.tasks]

            if existing:
                existing.title = p.title
                existing.subtitle = p.subtitle
                existing.difficulty = p.difficulty
                existing.category = p.category
                existing.tags = p.tags
                existing.estimated_minutes = p.estimated_minutes
                existing.problem_statement = p.problem_statement
                existing.system_context = p.system_context
                existing.ai_failure_mode = p.ai_failure_mode
                existing.starter_files = starter_files_json
                existing.tasks = tasks_json
            else:
                db.add(
                    ProjectRecord(
                        id=p.id,
                        title=p.title,
                        subtitle=p.subtitle,
                        difficulty=p.difficulty,
                        category=p.category,
                        tags=p.tags,
                        estimated_minutes=p.estimated_minutes,
                        problem_statement=p.problem_statement,
                        system_context=p.system_context,
                        ai_failure_mode=p.ai_failure_mode,
                        starter_files=starter_files_json,
                        tasks=tasks_json,
                    )
                )
        db.commit()
        return db.query(ProjectRecord).count()


def list_projects_from_db(db: Session) -> List[ProjectSummary]:
    records = db.query(ProjectRecord).order_by(ProjectRecord.created_at.asc()).all()
    return [record_to_summary(r) for r in records]


def get_project_from_db(db: Session, project_id: str) -> Optional[Project]:
    record = db.query(ProjectRecord).filter(ProjectRecord.id == project_id).first()
    if not record:
        return None
    return record_to_project(record)

