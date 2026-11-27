"""The pinned mini-swe-agent package layout, shared by tasks and migration."""
import ast
import copy
from pathlib import Path

PACKAGE = 'src/minisweagent/'
MODEL = PACKAGE + 'models/litellm_model.py'
AGENT = PACKAGE + 'agents/default.py'
LOCAL = PACKAGE + 'environments/local.py'
DOCKER = PACKAGE + 'environments/docker.py'
ACTIONS = PACKAGE + 'models/utils/actions_toolcall.py'
RETRY = PACKAGE + 'models/utils/retry.py'
EXCEPTIONS = PACKAGE + 'exceptions.py'
SERIALIZE = PACKAGE + 'utils/serialize.py'
APPROVAL = PACKAGE + 'agents/utils/prompt_user.py'
INSPECTOR = PACKAGE + 'run/utilities/inspector.py'
GUIDE = 'docs/index.md'
FIXTURE = 'tests/test_data/buggy_repository'

TASK_PATHS = {
    **dict.fromkeys(['model'], MODEL),
    **dict.fromkeys(['agent', 'conversation', 'conversation-loop', 'prompts', 'prompt-template', 'exploration', 'autonomous-loop', 'completion', 'repair-test', 'budgets'], AGENT),
    **dict.fromkeys(['command-execution', 'command-output', 'command-timeouts', 'filesystem', 'environment-secrets', 'network'], LOCAL),
    **dict.fromkeys(['tool-schema', 'tool-binding', 'tool-arguments', 'tool-feedback', 'malformed-tools'], ACTIONS),
    **dict.fromkeys(['docker-environment', 'container-start', 'provision', 'container-execution', 'lifecycle', 'resource-isolation'], DOCKER),
    **dict.fromkeys(['api-retries', 'backoff'], RETRY),
    **dict.fromkeys(['exceptions'], EXCEPTIONS),
    **dict.fromkeys(['token-usage', 'output-truncation', 'compaction', 'working-memory', 'trajectory-save', 'session-restore'], SERIALIZE),
    'approval': APPROVAL, 'git-diff': INSPECTOR,
}
RENAMES = {'Model': 'LitellmModel', 'ConversationAgent': 'DefaultAgent'}
LEGACY_IMPORTS = {
    'phase_core': 'minisweagent.models.litellm_model',
    'phase_shell': 'minisweagent.environments.local',
    'phase_tools': 'minisweagent.models.utils.actions_toolcall',
    'phase_autonomy': 'minisweagent.agents.default',
    'phase_docker': 'minisweagent.environments.docker',
    'phase_memory': 'minisweagent.utils.serialize',
    'phase_security': 'minisweagent.environments.local',
    'phase_reliability': 'minisweagent.models.utils.retry',
}


def module_name(path):
    return path.removeprefix('src/').removesuffix('.py').replace('/', '.')


def task_symbols(spec):
    return ['.'.join(RENAMES.get(part, part) for part in symbol.split('.')) for symbol in spec[2]]


def rewrite_copy(text):
    """Update lesson paths and names without changing the behavior contract."""
    for old, path in [('phase_core.py', MODEL), ('phase_tools.py', ACTIONS), ('phase_shell.py', LOCAL),
                      ('phase_autonomy.py', AGENT), ('phase_docker.py', DOCKER),
                      ('phase_reliability.py', RETRY), ('phase_memory.py', SERIALIZE),
                      ('phase_security.py', APPROVAL), ('COURSE.md', GUIDE), ('buggy_repository/', FIXTURE + '/')]:
        text = text.replace(old, path)
    for old, new in LEGACY_IMPORTS.items():
        text = text.replace(old + '.', new + '.')
    import re
    for old, new in RENAMES.items():
        text = re.sub(r'\b' + old + r'\b', new, text)
    return text


class PackageImports(ast.NodeTransformer):
    def visit_Name(self, node):
        if node.id in RENAMES:
            node.id = RENAMES[node.id]
        return node

    def visit_ClassDef(self, node):
        node.name = RENAMES.get(node.name, node.name)
        return self.generic_visit(node)

    def visit_ImportFrom(self, node):
        # Some legacy modules combined components now placed in separate files.
        if node.module in LEGACY_IMPORTS:
            old = node.module
            node.module = LEGACY_IMPORTS[old]
            for alias in node.names:
                alias.name = RENAMES.get(alias.name, alias.name)
            if old == 'phase_reliability':
                # Imports of exceptions belong to the exception module.
                if all(alias.name in {'TransientAPIError', 'LimitsExceeded', 'MalformedToolCall', 'classify_error'} for alias in node.names):
                    node.module = 'minisweagent.exceptions'
        return node


def transform_source(source):
    return ast.unparse(PackageImports().visit(ast.parse(source))) + '\n'


def repository_solutions(root=None):
    """Place teaching implementations in their corresponding upstream modules."""
    root = root or Path(__file__).resolve().parent.parent / 'curricula/mini_swe_agent'
    from app.mini_swe_tasks import TASK_SPECS
    groups = {}
    nodes = {}
    for spec in TASK_SPECS:
        key, logical, symbols, *_ = spec
        if logical not in nodes:
            nodes[logical] = ast.parse((root / 'solutions' / f'phase_{logical}.py').read_text(encoding='utf-8'))
        destination = TASK_PATHS[key]
        group = groups.setdefault(destination, {})
        for symbol in symbols:
            top = symbol.split('.')[0]
            node = next(n for n in nodes[logical].body if getattr(n, 'name', None) == top)
            group.setdefault((logical, top), copy.deepcopy(node))
    # Exception type declarations are supplied boilerplate; classification is a task.
    for node in nodes['reliability'].body:
        if isinstance(node, ast.ClassDef):
            groups[EXCEPTIONS][('reliability', node.name)] = copy.deepcopy(node)
    imports = {
        MODEL: 'from copy import deepcopy',
        AGENT: 'import math\nfrom copy import deepcopy\nfrom minisweagent.models.utils.actions_toolcall import tool_turn\nfrom minisweagent.exceptions import LimitsExceeded',
        LOCAL: 'import os\nimport signal\nimport subprocess\nimport math\nfrom pathlib import Path',
        DOCKER: 'import subprocess\nimport uuid\nfrom pathlib import Path',
        ACTIONS: 'import json\nfrom copy import deepcopy\nfrom minisweagent.environments.local import execute, normalize_result\nfrom minisweagent.exceptions import MalformedToolCall',
        RETRY: 'import time\nfrom minisweagent.exceptions import TransientAPIError',
        EXCEPTIONS: '',
        SERIALIZE: 'import json\nfrom copy import deepcopy\nfrom pathlib import Path',
        APPROVAL: 'from minisweagent.environments.local import authorize_network',
        INSPECTOR: '',
    }
    result = {}
    for path, group in groups.items():
        body = ast.parse(imports[path]).body + list(group.values())
        tree = PackageImports().visit(ast.Module(body=body, type_ignores=[]))
        # Remove a legacy self-import from safe_tool after moving it beside the parser.
        if path == ACTIONS:
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name == 'safe_tool':
                    node.body = [line for line in node.body if not (isinstance(line, ast.ImportFrom) and line.module == module_name(ACTIONS))]
        result[path] = ast.unparse(tree) + '\n'
    # The viewer is a supplied utility in the same location as upstream's inspector.
    viewer = (root / 'starter/course_app.py').read_text(encoding='utf-8')
    viewer = transform_source(viewer).replace("Path(__file__).parent / 'buggy_repository'", "Path.cwd() / 'tests/test_data/buggy_repository'")
    result[INSPECTOR] += '\n' + viewer
    return result


LEGACY_PATHS = {
    *[f'phase_{name}.py' for name in ['setup', 'core', 'shell', 'tools', 'autonomy', 'docker', 'reliability', 'memory', 'security']],
    'model.py', 'agent.py', 'environment.py', 'parser.py', 'trajectory.py', 'evaluation.py',
    'app.py', 'demo.py', 'course_app.py', 'COURSE.md', 'PHASES.md', 'PRESENTATION.md', 'templates/index.html',
    'upstream/default.py', 'upstream/local.py', 'upstream/protocols.py', 'upstream/LICENSE.md', 'upstream/source.json',
    'buggy_repository/calculator.py', 'buggy_repository/test_calculator.py',
}


def migrate_workspace_sources(previous, catalogue, merge):
    """Move old components into the package without executing learner code."""
    from app.mini_swe_tasks import TASK_SPECS
    authored = {file.path: file.content for file in catalogue.starter_files}
    supplied = {file.path for file in catalogue.starter_files if file.read_only}
    migrated = {path: content for path, content in previous.items() if path not in LEGACY_PATHS}
    for path, scaffold in authored.items():
        if path in supplied:
            migrated[path] = scaffold
        elif path in migrated and path.endswith('.py'):
            migrated[path] = merge(migrated[path], scaffold)
        else:
            migrated.setdefault(path, scaffold)
    for logical in sorted({spec[1] for spec in TASK_SPECS}):
        path = f'phase_{logical}.py'
        if path not in previous:
            continue
        destinations = {}
        for spec in TASK_SPECS:
            if spec[1] == logical:
                for symbol in spec[2]:
                    destinations[symbol.split('.')[0]] = TASK_PATHS[spec[0]]
        if logical == 'reliability':
            destinations.update({name: EXCEPTIONS for name in ['TransientAPIError', 'LimitsExceeded', 'MalformedToolCall']})
        try:
            tree = ast.parse(previous[path])
        except SyntaxError:
            # Keep an in-progress invalid draft in its principal component;
            # its complete original text also remains in the checkpoint.
            destination = next(iter(destinations.values()))
            if destination not in previous:
                import re
                text = previous[path]
                for old, new in LEGACY_IMPORTS.items():
                    text = re.sub(r'(?<=from )' + re.escape(old) + r'\b', new, text)
                for old, new in RENAMES.items():
                    text = re.sub(r'\b' + old + r'\b', new, text)
                migrated[destination] = text
            continue
        imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        groups = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                destination = destinations.get(node.name, next(iter(destinations.values())))
                groups.setdefault(destination, []).append(node)
        for destination, body in groups.items():
            if destination in previous:
                continue  # A learner's existing canonical file takes priority.
            fragment = ast.Module(body=copy.deepcopy(imports + body), type_ignores=[])
            fragment = PackageImports().visit(fragment)
            migrated[destination] = merge(ast.unparse(fragment), migrated[destination])
    for name in ['calculator.py', 'test_calculator.py']:
        old = 'buggy_repository/' + name
        new = FIXTURE + '/' + name
        if old in previous and new not in previous:
            migrated[new] = previous[old]
    return migrated
