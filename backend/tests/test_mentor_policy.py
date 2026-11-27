import unittest
from types import SimpleNamespace

from app.mentor_policy import MentorPolicy, contains_code


class MentorPolicyTests(unittest.TestCase):
    def test_unlock_is_local_to_the_persisted_task(self):
        session = SimpleNamespace(hint_levels={'first': 4, 'second': 3})
        self.assertTrue(MentorPolicy.for_task(session, 'first').code_unlocked)
        self.assertFalse(MentorPolicy.for_task(session, 'second').code_unlocked)
        self.assertFalse(MentorPolicy.for_task(session, 'new').code_unlocked)
        self.assertTrue(MentorPolicy.for_task(session, 'second', next_hint=True).code_unlocked)
        self.assertEqual(session.hint_levels['second'], 3)

    def test_guard_rejects_code_forms_and_allows_conceptual_guidance(self):
        for content in (
            '```python\nreturn True\n```', '~~~js\nconst x = 1\n~~~',
            'Use `deepcopy(messages)` here.', 'messages = deepcopy(history)',
            'Call deepcopy(messages) before forwarding.', 'import copy',
            'def query(self):', 'if ready:\n    return True', 'return result',
            'SELECT name FROM users', '{"role": "assistant"}',
            'python -m pytest', 'docker run image', 'items[0]', '[1, 2]',
            '<script>alert(1)</script>', 'The check is current == expected.',
        ):
            with self.subTest(content=content):
                self.assertTrue(contains_code(content))
        for content in (
            'A deep copy duplicates nested data, so later edits stay independent.',
            'In query, copy the conversation before passing it to the provider.',
            '1. Read the current time.\n2. Compare it with the request time.',
            'Inspect [default.py:42](#code?path=src%2Fminisweagent%2Fagents%2Fdefault.py&line=42).',
            'A timestamp records when something happened.',
        ):
            with self.subTest(content=content):
                self.assertFalse(contains_code(content))
