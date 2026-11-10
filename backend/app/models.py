from typing import List, Optional, Literal
from pydantic import BaseModel


class ProjectFile(BaseModel):
    path: str
    language: str
    content: str
    read_only: bool = False


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

