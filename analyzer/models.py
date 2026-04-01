from dataclasses import dataclass


@dataclass
class Issue:
    """
    Represents one issue found in the code.
    """
    issue_type: str          # e.g. "unreachable_code", "unused_variable"
    line: int                # line number in the source code
    summary: str             # short title
    explanation: str         # longer explanation in plain English
    severity: str = "warning"  # "info", "warning", "error"
