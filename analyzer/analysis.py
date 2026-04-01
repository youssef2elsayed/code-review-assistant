import ast
from typing import List

from .models import Issue
from .rules import run_all_rules
from .cpp_analysis import analyze_cpp_code
from .js_analysis import analyze_js_code


def _analyze_python_code(source: str) -> List[Issue]:
    """
    Python analysis using the AST and rule engine.
    """
    issues: List[Issue] = []

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        line = e.lineno or 1
        summary = "Syntax error"
        explanation = (
            f"The Python code contains a syntax error on or near line {line}: {e.msg}. "
            f"Fix this error first before addressing other issues."
        )
        issues.append(
            Issue(
                issue_type="syntax_error",
                line=line,
                summary=summary,
                explanation=explanation,
                severity="error",
            )
        )
        return issues

    issues.extend(run_all_rules(tree))
    issues.sort(key=lambda i: i.line)
    return issues


def analyze_code(source: str, language: str) -> List[Issue]:
    """
    Dispatch analysis based on the selected language.
    Supported: Python, C++, JavaScript.
    """
    language_normalised = (language or "python").strip().lower()

    if language_normalised in ("python", "py"):
        return _analyze_python_code(source)

    if language_normalised in ("c++", "cpp"):
        return analyze_cpp_code(source)

    if language_normalised in ("javascript", "js"):
        return analyze_js_code(source)

    # Fallback for unsupported language
    return [
        Issue(
            issue_type="unsupported_language",
            line=1,
            summary="Unsupported language",
            explanation=(
                f"The language '{language}' is not supported yet. "
                f"Supported languages are: Python, C++, and JavaScript."
            ),
            severity="error",
        )
    ]
