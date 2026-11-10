import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class UserRecord(Base):
    """
    Mirrors authenticated Supabase users in our application schema.
    `id` corresponds to the Supabase Auth user UUID (`sub` claim in JWT).
    """

    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    workspace_sessions = relationship(
        "WorkspaceSessionRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class ProjectRecord(Base):
    """
    Stores engineering challenge projects, starter file trees, and tasks using native JSONB.
    """

    __tablename__ = "projects"

    id = Column(String(128), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    subtitle = Column(String(512), nullable=False)
    difficulty = Column(String(32), nullable=False)
    category = Column(String(128), nullable=False)
    tags = Column(JSONB, nullable=False, default=list)
    estimated_minutes = Column(Integer, nullable=False, default=45)
    problem_statement = Column(Text, nullable=False)
    system_context = Column(Text, nullable=False)
    ai_failure_mode = Column(Text, nullable=False)
    starter_files = Column(JSONB, nullable=False, default=list)
    tasks = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    workspace_sessions = relationship(
        "WorkspaceSessionRecord",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class WorkspaceSessionRecord(Base):
    """
    Persists a user's live IDE workspace state for a specific project:
    - `files`: Current virtual file tree (starter edits + user-created files)
    - `active_file_path`: Last focused editor tab
    - `active_task_id`: Current task selected in the compact task header
    - `completed_task_ids`: List of verified task IDs
    - `hint_levels`: Dict mapping `task_id -> 0..4` (3 hints + 4th solution reveal)
    - `last_verification`: Latest test & AI evaluation report per task
    """

    __tablename__ = "workspace_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", name="uq_user_project_session"),
    )

    id = Column(String(64), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        String(128),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    files = Column(JSONB, nullable=False, default=list)
    active_file_path = Column(String(255), nullable=True)
    active_task_id = Column(String(128), nullable=True)
    completed_task_ids = Column(JSONB, nullable=False, default=list)
    hint_levels = Column(JSONB, nullable=False, default=dict)
    last_verification = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user = relationship("UserRecord", back_populates="workspace_sessions")
    project = relationship("ProjectRecord", back_populates="workspace_sessions")
    chat_messages = relationship(
        "ChatMessageRecord",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessageRecord.created_at",
    )


class ChatMessageRecord(Base):
    """
    Stores the AI side chat history and progressive hints for a workspace session.
    `message_type`: 'chat' | 'hint_1' | 'hint_2' | 'hint_3' | 'solution' | 'evaluation'
    """

    __tablename__ = "chat_messages"

    id = Column(String(64), primary_key=True, default=generate_uuid, index=True)
    session_id = Column(
        String(64),
        ForeignKey("workspace_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id = Column(String(128), nullable=True, index=True)
    role = Column(String(32), nullable=False)  # 'user' | 'assistant' | 'system'
    message_type = Column(String(32), nullable=False, default="chat")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("WorkspaceSessionRecord", back_populates="chat_messages")

