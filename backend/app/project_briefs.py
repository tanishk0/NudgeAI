"""Authored briefing metadata is kept with curriculum, never inferred by an LLM."""
BRIEFS = {
    "flawed-ai-payment-webhook": {
        "technologies": ["Python", "HMAC / SHA-256", "threading", "Webhooks"],
        "learning_outcomes": ["Verify signed webhook requests and reject replays", "Prevent duplicate credits with atomic idempotency", "Test failure paths in a payment workflow"],
        "prerequisites": ["Python functions and dictionaries", "Basic HTTP and API concepts"],
        "deliverable": "A payment webhook handler that validates signatures, rejects stale requests, and processes duplicate events safely.",
        "runtime": {"entrypoint": "webhook_service.py", "mode": "script"},
    },
    "rag-prompt-injection-firewall": {
        "technologies": ["Python", "RAG", "Multi-tenant retrieval", "Prompt design"],
        "learning_outcomes": ["Scope document retrieval to an authenticated tenant", "Separate retrieved data from model instructions", "Recognize prompt injection across trust boundaries"],
        "prerequisites": ["Python lists and dictionaries", "An understanding of LLM prompts"],
        "deliverable": "A tenant-scoped retrieval pipeline with explicit boundaries around untrusted document content.",
        "runtime": {"entrypoint": "rag_pipeline.py", "mode": "script"},
    },
    "n-plus-one-connection-pool-collapse": {
        "technologies": ["Python", "Query batching", "Data structures"],
        "learning_outcomes": ["Recognize N+1 query patterns", "Batch related data into a single query", "Preserve response behavior while reducing database calls"],
        "prerequisites": ["Python loops and dictionaries", "Basic database queries"],
        "deliverable": "A team dashboard aggregation that produces the same results in two database queries.",
        "runtime": {"entrypoint": "dashboard_api.py", "mode": "script"},
    },
    "vulpy-security-review": {
        "technologies": ["Python", "Flask", "SQLite", "scrypt", "HTML"],
        "learning_outcomes": ["Replace SQL interpolation with parameterized queries", "Hash passwords and authenticate password changes", "Sign sessions and generate secure API keys", "Escape user content and apply security headers"],
        "prerequisites": ["Comfort with Python modules", "HTTP cookies and SQL basics", "Basic HTML"],
        "deliverable": "A hardened microblog library with six security findings addressed and verified.",
        "runtime": {"entrypoint": "vulpy_app.py", "mode": "web", "port": 5000, "path": "/posts/admin"},
    },
}


def enrich_project(project):
    if project.id == "build-mini-swe-agent":
        from app.projects_mini_swe import MINI_SWE_PROJECT
        for key in ("technologies", "learning_outcomes", "prerequisites", "deliverable", "runtime"):
            setattr(project, key, getattr(MINI_SWE_PROJECT, key))
    if project.id == "build-devshelf":
        from app.projects_launchpad import LAUNCHPAD_PROJECT
        for key in ("technologies", "learning_outcomes", "prerequisites", "deliverable", "runtime"):
            setattr(project, key, getattr(LAUNCHPAD_PROJECT, key))
    for key, value in BRIEFS.get(project.id, {}).items():
        setattr(project, key, value)
    return refresh_learning_copy(project)


def refresh_learning_copy(project):
    """Improve wording for existing workspaces without resetting code or progress."""
    if project.id == 'build-mini-swe-agent':
        from app.projects_mini_swe import SPECS
        from app.mini_swe_walkthroughs import lesson_brief
        specs = {'mini-swe-' + spec[0]: spec for spec in SPECS}
        for task in project.tasks:
            spec = specs.get(task.id)
            if spec and task.target_file == spec[1]:
                task.title = spec[3]
                task.objective = spec[4]
                task.instructions = lesson_brief(spec[0], spec[1], spec[2], task.order, len(project.tasks), spec[5])
        from app.mini_swe_phases import attach_concepts
        attach_concepts(project)
    return project
