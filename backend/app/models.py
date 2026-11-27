from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from app.file_policy import normalize_path, validate_files


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

    _valid_path = field_validator("path")(normalize_path)


class TaskFile(BaseModel):
    path: str
    purpose: Literal['edit', 'reference'] = 'reference'


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
    task_files: List[TaskFile] = Field(default_factory=list)
    phase: Optional[int] = None
    estimated_time: str = ""
    concept_markdown: str = ""
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
    version: str = ""
    technologies: List[str] = Field(default_factory=list)
    learning_outcomes: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    deliverable: str = ""
    runtime: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def describe_task_files(self):
        # Also enrich saved course versions that predate task file lists.
        import re
        available = {f.path: f for f in self.starter_files}
        mini_references = {
            'model-setup': [], 'model': [], 'history': [], 'agent-setup': [],
            'parse': [], 'execute': [], 'timeout': [], 'completion': [],
            'limits': [], 'accounting': ['model.py'],
            'step': ['model.py', 'parser.py', 'environment.py'],
            'recovery': ['parser.py'], 'serialize': [], 'save': [],
            'run': ['model.py', 'parser.py', 'environment.py', 'trajectory.py'],
            'verify': ['environment.py', 'demo.py'],
            'phase-core': ['PHASES.md'],
            'phase-tools': ['phase_core.py', 'environment.py', 'PHASES.md'],
            'phase-autonomy': ['phase_core.py', 'phase_tools.py', 'environment.py', 'buggy_repository/calculator.py', 'buggy_repository/test_calculator.py'],
            'phase-docker': ['PHASES.md'],
            'phase-reliability': ['phase_tools.py', 'environment.py', 'PHASES.md'],
            'phase-memory': ['trajectory.py', 'PHASES.md'],
            'phase-security': ['phase_docker.py', 'PHASES.md'],
        }
        for task in self.tasks:
            if task.task_files:
                continue
            references = re.findall(r'`([^`\n]+)`', task.instructions)
            if task.id.startswith('mini-swe-'):
                references += mini_references.get(task.id.removeprefix('mini-swe-'), [])
            else:
                # Include local modules used by the target, without listing libraries.
                import ast
                source = available.get(task.target_file)
                if source and source.language == 'python':
                    try:
                        tree = ast.parse(source.content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ImportFrom) and node.module:
                                references.append(node.module.replace('.', '/') + '.py')
                            elif isinstance(node, ast.Import):
                                references.extend(alias.name.replace('.', '/') + '.py' for alias in node.names)
                    except SyntaxError:
                        pass
            paths = list(dict.fromkeys([task.target_file, *references]))
            task.task_files = [TaskFile(path=path, purpose='edit' if path == task.target_file and not available[path].read_only else 'reference') for path in paths if path in available]
        return self


class PublicTask(BaseModel):
    id: str
    order: int
    title: str
    category: str
    objective: str
    instructions: str
    validation_criteria: List[str]
    target_file: str
    task_files: List[TaskFile] = Field(default_factory=list)
    phase: Optional[int] = None
    estimated_time: str = ""
    concept_markdown: str = ""


class PublicProject(Project):
    tasks: List[PublicTask]  # type: ignore[assignment]


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
    project: PublicProject
    revision: int = 0
    content_hash: str = ""
    files: List[WorkspaceFile]
    active_file_path: str
    active_task_id: str
    completed_task_ids: List[str] = Field(default_factory=list)
    unlocked_task_ids: List[str] = Field(default_factory=list)
    hint_levels: Dict[str, int] = Field(default_factory=dict)
    last_verification: Dict[str, Any] = Field(default_factory=dict)
    chat_messages: List[ChatMessageItem] = Field(default_factory=list)


class RevisionRequest(BaseModel):
    expected_revision: int = Field(ge=0)


class UpdateWorkspaceStateRequest(RevisionRequest):
    files: Optional[List[WorkspaceFile]] = None
    active_file_path: Optional[str] = None
    active_task_id: Optional[str] = None

    @model_validator(mode="after")
    def check_files(self):
        if self.files is not None:
            validate_files(self.files)
        return self


class CreateFileRequest(RevisionRequest):
    path: str
    content: str = ""
    language: Optional[str] = None
    _valid_path = field_validator("path")(normalize_path)


class RenameFileRequest(RevisionRequest):
    old_path: str
    new_path: str
    _valid_path = field_validator("old_path", "new_path")(normalize_path)


class ResetWorkspaceRequest(RevisionRequest):
    reset_progress: bool = False


class CriterionEvaluation(BaseModel):
    criterion: str
    passed: bool
    reason: str


class TaskVerificationReport(BaseModel):
    task_id: str
    passed_all: bool
    sandbox_passed: bool
    execution_status: Literal['completed', 'error'] = 'completed'
    sandbox_output: str
    execution_ms: int
    criteria_results: List[CriterionEvaluation]
    architectural_feedback: str
    verified_at: str
    content_hash: str = ""
    revision: int = 0


class VerifyTaskRequest(RevisionRequest):
    task_id: str
    files: Optional[List[WorkspaceFile]] = None


class RequestNudgePayload(RevisionRequest):
    task_id: str
    active_file_path: Optional[str] = None
    files: Optional[List[WorkspaceFile]] = None


class SendChatPayload(RevisionRequest):
    task_id: str
    active_file_path: Optional[str] = None
    message: str = Field(min_length=1, max_length=6000)
    files: Optional[List[WorkspaceFile]] = None


