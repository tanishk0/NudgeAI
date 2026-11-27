"""Distinguish evaluated assertions from an incomplete checker run."""


def execution_failed(report):
    if report.get('execution_status') == 'error':
        return True
    criteria = report.get('criteria_results') or []
    def reason(item):
        return item.get('reason', '') if isinstance(item, dict) else item.reason
    return bool(criteria) and all(reason(item).startswith((
        'Execution failed before verification completed.', 'Not evaluated:')) for item in criteria)


INCOMPLETE_FEEDBACK = (
    'The checker could not complete, so there is no test verdict for this run. '
    'Retry Check task and inspect the execution logs if it happens again. '
    'This result does not establish a missing behavior in your implementation.'
)
