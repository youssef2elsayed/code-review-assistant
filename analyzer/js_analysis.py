import re
from typing import List, Dict

from .models import Issue


def _detect_unused_variables_js(lines: List[str]) -> List[Issue]:
    """
    Simple JavaScript unused variable detection:
    - Looks for single declarations like:
      let x;
      const y = 1;
      var z = 0;
    - Checks whether the variable name appears anywhere else.
    """
    issues: List[Issue] = []
    decl_pattern = re.compile(
        r'^\s*(var|let|const)\s+([a-zA-Z_]\w*)\s*(=|;|\[)'
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
                f"The variable '{name}' is declared at line {decl_line} but does not seem to be used "
                f"anywhere else in the file. "
                f"Remove it or use it if it was intended."
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


def _detect_long_functions_js(lines: List[str], max_lines: int = 40) -> List[Issue]:
    """
    Roughly detect long JS functions:
    - Looks for lines starting with 'function' or containing 'function name('
    - Counts non-empty lines until the matching closing brace.
    """
    issues: List[Issue] = []

    func_decl_pattern = re.compile(r'^\s*function\s+[a-zA-Z_]\w*\s*\([^)]*\)\s*\{')

    in_function = False
    brace_depth = 0
    function_start_line = 0
    function_line_count = 0

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not in_function and func_decl_pattern.match(line):
            in_function = True
            function_start_line = idx
            function_line_count = 0
            brace_depth = 1
            continue

        if in_function:
            brace_depth += line.count("{")
            brace_depth -= line.count("}")

            if stripped and stripped not in ["{", "}"]:
                function_line_count += 1

            if brace_depth <= 0:
                if function_line_count > max_lines:
                    summary = "Long function"
                    explanation = (
                        f"This JavaScript function starting at line {function_start_line} "
                        f"has about {function_line_count} lines of code, "
                        f"which is longer than the recommended {max_lines}. "
                        f"Consider splitting it into smaller, focused functions."
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


def analyze_js_code(source: str) -> List[Issue]:
    """
    Entry point for JavaScript analysis.
    Heuristic, but useful for beginner-style code.
    """
    lines = source.splitlines()
    issues: List[Issue] = []

    issues.extend(_detect_unused_variables_js(lines))
    issues.extend(_detect_long_functions_js(lines, max_lines=40))

    issues.sort(key=lambda i: i.line)
    return issues
