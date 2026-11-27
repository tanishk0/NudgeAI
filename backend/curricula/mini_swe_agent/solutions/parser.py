import re


class FormatError(ValueError):
    pass


def parse_action(content):
    """Require exactly one nonempty fenced bash block and return its command."""
    if not isinstance(content, str):
        raise FormatError("Response content must be text")
    blocks = re.findall(r"```bash\s*\n(.*?)```", content, re.DOTALL)
    if len(blocks) != 1 or content.count("```") != 2 or not blocks[0].strip():
        raise FormatError("Return exactly one nonempty ```bash block")
    return {"command": blocks[0].strip()}
