import re
from typing import List, Dict

from .models import Issue


def _detect_unused_variables(lines: List[str]) -> List[Issue]:
    """
    Very simple C++ unused variable detection:
    - Looks for single-variable declarations like:
      int x;
      double value = 0;
    - Then checks whether the variable name appears anywhere else.
    """
    issues: List[Issue] = []
    decl_pattern = re.compile(
        r'^\s*(int|float|double|char|bool|string|auto)\s+([a-zA-Z_]\w*)\s*(=|;|\[)'
    )

    declarations: Dict[str, int] = {}
    for idx, line in enumerate(lines, start=1):
        m = decl_pattern.match(line)
        if m:
            name = m.group(2)
            declarations[name] = idx

    for name, decl_line in declarations.items():
        used = False
        for idx, line in enumerate(lines, start=1):
            if idx == decl_line:
                continue
            if re.search(r'\b' + re.escape(name) + r'\b', line):
                used = True
                break
        if not used:
            summary = "Unused variable"
            explanation = (
                f"The variable '{name}' appears to be declared at line {decl_line} "
                f"but is not used elsewhere in the file. "
                f"Unused variables can indicate leftover or confusing code."
            )
            issues.append(
                Issue(
                    issue_type="unused_variable",
                    line=decl_line,
                    summary=summary,
                    explanation=explanation,
                    severity="info",
                )
            )

    return issues


def _detect_long_functions(lines: List[str], max_lines: int = 40) -> List[Issue]:
    """
    Approximate detection of very long C++ functions by counting the number
    of non-empty lines between a function opening '{' and its matching '}'.
    """
    issues: List[Issue] = []

    brace_depth = 0
    in_function = False
    function_start_line = 0
    function_line_count = 0

    # Very rough function signature pattern (will not catch all forms, but fine for student code)
    func_decl_pattern = re.compile(r'^\s*[a-zA-Z_][\w:<>\s*&]*\s+[a-zA-Z_]\w*\s*\([^;]*\)\s*\{')

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Detect probable function start
        if not in_function and func_decl_pattern.match(line):
            in_function = True
            function_start_line = idx
            function_line_count = 0
            brace_depth = 1
            continue

        if in_function:
            # Track braces
            brace_depth += line.count("{")
            brace_depth -= line.count("}")

            # Count non-empty, non-brace-only lines as "content"
            if stripped and stripped not in ["{", "}"]:
                function_line_count += 1

            # If we've closed the function
            if brace_depth <= 0:
                if function_line_count > max_lines:
                    summary = "Long function"
                    explanation = (
                        f"This C++ function starting at line {function_start_line} "
                        f"contains approximately {function_line_count} lines of code, "
                        f"which is more than the recommended {max_lines}. "
                        f"Consider splitting it into smaller functions with clearer responsibilities."
                    )
                    issues.append(
                        Issue(
                            issue_type="long_function",
                            line=function_start_line,
                            summary=summary,
                            explanation=explanation,
                            severity="info",
                        )
                    )
                in_function = False
                brace_depth = 0

    return issues


def analyze_cpp_code(source: str) -> List[Issue]:
    """
    Entry point for C++ analysis.
    This is intentionally simpler than the Python AST analysis:
    - Uses regex + line-based heuristics.
    - Focuses on beginner-style issues: unused variables and long functions.
    """
    lines = source.splitlines()
    issues: List[Issue] = []

    issues.extend(_detect_unused_variables(lines))
    issues.extend(_detect_long_functions(lines, max_lines=40))

    issues.sort(key=lambda i: i.line)
    return issues
