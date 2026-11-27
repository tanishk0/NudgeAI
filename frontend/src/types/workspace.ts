export interface WorkspaceFile {
  path: string
  language: string
  content: string
  read_only: boolean
  is_starter: boolean
}

export interface TaskItem {
  id: string
  order: number
  title: string
  category: 'debugging' | 'security' | 'architecture' | 'performance'
  objective: string
  instructions: string
  validation_criteria: string[]
  target_file: string
  task_files: { path: string; purpose: 'edit' | 'reference' }[]
  phase?: number | null
  estimated_time?: string
  concept_markdown?: string
}

export interface ProjectDetail {
  id: string
  title: string
  subtitle: string
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced'
  category: string
  tags: string[]
  estimated_minutes: number
  problem_statement: string
  system_context: string
  ai_failure_mode: string
  starter_files: WorkspaceFile[]
  tasks: TaskItem[]
  version: string
  technologies: string[]
  learning_outcomes: string[]
  prerequisites: string[]
  deliverable: string
  runtime: { mode: 'script' | 'web'; entrypoint: string; port?: number }
}

export interface ChatMessageItem {
  id: string
  task_id: string | null
  role: 'user' | 'assistant' | 'system'
  message_type:
    'chat' | 'hint_1' | 'hint_2' | 'hint_3' | 'solution' | 'evaluation'
  content: string
  created_at: string
}

export interface CriterionEvaluation {
  criterion: string
  passed: boolean
  reason: string
}

export interface TaskVerificationReport {
  task_id: string
  passed_all: boolean
  sandbox_passed: boolean
  execution_status?: 'completed' | 'error'
  sandbox_output: string
  execution_ms: number
  criteria_results: CriterionEvaluation[]
  architectural_feedback: string
  verified_at?: string
  content_hash?: string
  revision?: number
}

export interface WorkspaceSessionResponse {
  session_id: string
  revision: number
  content_hash: string
  project: ProjectDetail
  files: WorkspaceFile[]
  active_file_path: string
  active_task_id: string
  completed_task_ids: string[]
  unlocked_task_ids: string[]
  hint_levels: Record<string, number>
  last_verification: Record<string, TaskVerificationReport>
  chat_messages: ChatMessageItem[]
}

export interface RuntimeResult {
  status: 'running' | 'finished' | 'failed' | 'stopped'
  revision: number
  output: string
  exit_code?: number | null
  preview_url?: string
}

export interface Checkpoint {
  id: string
  label: string
  revision: number
  created_at: string
}
