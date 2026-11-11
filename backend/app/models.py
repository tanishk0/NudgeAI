from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class ProjectFile(BaseModel):
    path: str
    language: str
    content: str
    read_only: bool = False


class WorkspaceFile(BaseModel):
    path: str
    language: str
    content: str
    read_only: bool = False
    is_starter: bool = True


class TaskItem(BaseModel):
    id: str
    order: int
    title: str
    category: Literal["debugging", "security", "architecture", "performance"]
    objective: str
    instructions: str
    validation_criteria: List[str]
    hints: List[str]
    target_file: str
    # Mentor-only briefing (CWE/OWASP mapping, exploit mechanics, verifier
    # behaviour, common wrong fixes). Injected into the AI context packet.
    mentor_context: Optional[str] = None


class Project(BaseModel):
    id: str
    title: str
    subtitle: str
    difficulty: Literal["Beginner", "Intermediate", "Advanced"]
    category: str
    tags: List[str]
    estimated_minutes: int
    problem_statement: str
    system_context: str
    ai_failure_mode: str
    starter_files: List[ProjectFile]
    tasks: List[TaskItem]


class ProjectSummary(BaseModel):
    id: str
    title: str
    subtitle: str
    difficulty: Literal["Beginner", "Intermediate", "Advanced"]
    category: str
    tags: List[str]
    estimated_minutes: int
    ai_failure_mode: str
    task_count: int


class AuthenticatedUser(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class ChatMessageItem(BaseModel):
    id: str
    task_id: Optional[str] = None
    role: Literal["user", "assistant", "system"]
    message_type: Literal[
        "chat", "hint_1", "hint_2", "hint_3", "solution", "evaluation"
    ] = "chat"
    content: str
    created_at: str


class WorkspaceSessionResponse(BaseModel):
    session_id: str
    project: Project
    files: List[WorkspaceFile]
    active_file_path: str
    active_task_id: str
    completed_task_ids: List[str] = Field(default_factory=list)
    hint_levels: Dict[str, int] = Field(default_factory=dict)
    last_verification: Dict[str, Any] = Field(default_factory=dict)
    chat_messages: List[ChatMessageItem] = Field(default_factory=list)


class UpdateWorkspaceStateRequest(BaseModel):
    files: Optional[List[WorkspaceFile]] = None
    active_file_path: Optional[str] = None
    active_task_id: Optional[str] = None


class CreateFileRequest(BaseModel):
    path: str
    content: str = ""
    language: Optional[str] = None


class RenameFileRequest(BaseModel):
    old_path: str
    new_path: str


class ResetWorkspaceRequest(BaseModel):
    reset_progress: bool = False


class CriterionEvaluation(BaseModel):
    criterion: str
    passed: bool
    reason: str


class TaskVerificationReport(BaseModel):
    task_id: str
    passed_all: bool
    sandbox_passed: bool
    sandbox_output: str
    execution_ms: int
    criteria_results: List[CriterionEvaluation]
    architectural_feedback: str
    verified_at: str


class VerifyTaskRequest(BaseModel):
    task_id: str
    files: Optional[List[WorkspaceFile]] = None


class RequestNudgePayload(BaseModel):
    task_id: str
    active_file_path: Optional[str] = None
    files: Optional[List[WorkspaceFile]] = None


class SendChatPayload(BaseModel):
    task_id: str
    active_file_path: Optional[str] = None
    message: str
    files: Optional[List[WorkspaceFile]] = None


