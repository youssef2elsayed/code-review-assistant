import ast
from typing import List, Dict, Set

from .models import Issue


# -------------------------
# Helper visitors / checks
# -------------------------


class UnreachableCodeChecker:
    """
    Looks for unreachable statements after a return/raise/break/continue
    inside function bodies.
    """

    TERMINATING_NODES = (ast.Return, ast.Raise, ast.Break, ast.Continue)

    def run(self, tree: ast.AST) -> List[Issue]:
        issues: List[Issue] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                issues.extend(self._check_function_body(node))
        return issues

    def _check_function_body(self, func: ast.FunctionDef) -> List[Issue]:
        issues: List[Issue] = []
        body = func.body

        terminated = False
        for stmt in body:
            if terminated:
                # Anything after a terminating statement at same block level is unreachable
                line = getattr(stmt, "lineno", None)
                if line is not None:
                    summary = "Unreachable code"
                    explanation = (
                        f"Code at line {line} in function '{func.name}' is unreachable, "
                        f"because a return/raise/break/continue appears earlier in the same block. "
                        f"Consider removing it or restructuring the function."
                    )
                    issues.append(
                        Issue(
                            issue_type="unreachable_code",
                            line=line,
                            summary=summary,
                            explanation=explanation,
                            severity="warning",
                        )
                    )
            if isinstance(stmt, self.TERMINATING_NODES):
                terminated = True

        return issues


class NestingDepthChecker(ast.NodeVisitor):
    """
    Checks for deeply nested control structures (if/for/while/try).
    """

    CONTROL_NODES = (ast.If, ast.For, ast.While, ast.Try, ast.With)

    def __init__(self, max_depth: int = 3) -> None:
        self.max_depth = max_depth
        self.current_depth = 0
        self.issues: List[Issue] = []

    def generic_visit(self, node):
        is_control = isinstance(node, self.CONTROL_NODES)
        if is_control:
            self.current_depth += 1
            if self.current_depth > self.max_depth:
                line = getattr(node, "lineno", None)
                if line is not None:
                    summary = "Deeply nested logic"
                    explanation = (
                        f"This code block (starting at line {line}) is nested more than {self.max_depth} levels deep. "
                        f"Deep nesting makes code hard to read and maintain. "
                        f"Consider extracting parts into helper functions or simplifying the logic."
                    )
                    self.issues.append(
                        Issue(
                            issue_type="deep_nesting",
                            line=line,
                            summary=summary,
                            explanation=explanation,
                            severity="info",
                        )
                    )

        super().generic_visit(node)

        if is_control:
            self.current_depth -= 1


class LongFunctionChecker(ast.NodeVisitor):
    """
    Flags functions that are longer than a threshold number of statements.
    """

    def __init__(self, max_statements: int = 20) -> None:
        self.max_statements = max_statements
        self.issues: List[Issue] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Approximate: number of statements in the direct body
        num_statements = len(node.body)
        if num_statements > self.max_statements:
            line = getattr(node, "lineno", None)
            if line is not None:
                summary = "Long function"
                explanation = (
                    f"Function '{node.name}' has {num_statements} top-level statements, "
                    f"which is more than the recommended {self.max_statements}. "
                    f"Long functions are harder to test and understand. "
                    f"Consider splitting it into smaller helper functions with clear responsibilities."
                )
                self.issues.append(
                    Issue(
                        issue_type="long_function",
                        line=line,
                        summary=summary,
                        explanation=explanation,
                        severity="info",
                    )
                )
        self.generic_visit(node)


class VariableUsageVisitor(ast.NodeVisitor):
    """
    Collects assigned and used variables to detect unused ones.
    """

    def __init__(self) -> None:
        self.assigned: Dict[str, List[int]] = {}
        self.used: Set[str] = set()

    # Assignment: a = 1, x, y = ...
    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self._collect_assigned(target)
        self.generic_visit(node)

    # Walrus operator: (Python 3.8+): x := 1
    def visit_NamedExpr(self, node: ast.NamedExpr):
        self._collect_assigned(node.target)
        self.generic_visit(node)

    # Function arguments
    def visit_arg(self, node: ast.arg):
        name = node.arg
        line = getattr(node, "lineno", None)
        if line is not None:
            self.assigned.setdefault(name, []).append(line)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self.used.add(node.id)
        self.generic_visit(node)

    def _collect_assigned(self, target):
        if isinstance(target, ast.Name):
            name = target.id
            line = getattr(target, "lineno", None)
            if line is not None:
                self.assigned.setdefault(name, []).append(line)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._collect_assigned(elt)


def check_unused_variables(tree: ast.AST) -> List[Issue]:
    visitor = VariableUsageVisitor()
    visitor.visit(tree)

    issues: List[Issue] = []

    for name, lines in visitor.assigned.items():
        # Ignore "throwaway" names like "_" by convention
        if name == "_":
            continue
        if name not in visitor.used:
            first_line = lines[0]
            summary = "Unused variable"
            explanation = (
                f"The variable '{name}' is assigned at line {first_line} but never used afterwards. "
                f"Unused variables can confuse readers and may indicate leftover or incomplete code. "
                f"Consider removing it or using it if it was intended."
            )
            issues.append(
                Issue(
                    issue_type="unused_variable",
                    line=first_line,
                    summary=summary,
                    explanation=explanation,
                    severity="info",
                )
            )

    return issues


# -------------------------
# Entry point for all rules
# -------------------------


def run_all_rules(tree: ast.AST) -> List[Issue]:
    issues: List[Issue] = []

    # 1) Unreachable code
    unreachable_checker = UnreachableCodeChecker()
    issues.extend(unreachable_checker.run(tree))

    # 2) Deep nesting
    nesting_checker = NestingDepthChecker(max_depth=3)
    nesting_checker.visit(tree)
    issues.extend(nesting_checker.issues)

    # 3) Long functions
    long_func_checker = LongFunctionChecker(max_statements=20)
    long_func_checker.visit(tree)
    issues.extend(long_func_checker.issues)

    # 4) Unused variables
    issues.extend(check_unused_variables(tree))

    return issues
import ast
from typing import List, Dict, Set

from .models import Issue


# -------------------------
# Helper visitors / checks
# -------------------------


class UnreachableCodeChecker:
    """
    Looks for unreachable statements after a return/raise/break/continue
    inside function bodies.
    """

    TERMINATING_NODES = (ast.Return, ast.Raise, ast.Break, ast.Continue)

    def run(self, tree: ast.AST) -> List[Issue]:
        issues: List[Issue] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                issues.extend(self._check_function_body(node))
        return issues

    def _check_function_body(self, func: ast.FunctionDef) -> List[Issue]:
        issues: List[Issue] = []
        body = func.body

        terminated = False
        for stmt in body:
            if terminated:
                # Anything after a terminating statement at same block level is unreachable
                line = getattr(stmt, "lineno", None)
                if line is not None:
                    summary = "Unreachable code"
                    explanation = (
                        f"Code at line {line} in function '{func.name}' is unreachable, "
                        f"because a return/raise/break/continue appears earlier in the same block. "
                        f"Consider removing it or restructuring the function."
                    )
                    issues.append(
                        Issue(
                            issue_type="unreachable_code",
                            line=line,
                            summary=summary,
                            explanation=explanation,
                            severity="warning",
                        )
                    )
            if isinstance(stmt, self.TERMINATING_NODES):
                terminated = True

        return issues


class NestingDepthChecker(ast.NodeVisitor):
    """
    Checks for deeply nested control structures (if/for/while/try).
    """

    CONTROL_NODES = (ast.If, ast.For, ast.While, ast.Try, ast.With)

    def __init__(self, max_depth: int = 3) -> None:
        self.max_depth = max_depth
        self.current_depth = 0
        self.issues: List[Issue] = []

    def generic_visit(self, node):
        is_control = isinstance(node, self.CONTROL_NODES)
        if is_control:
            self.current_depth += 1
            if self.current_depth > self.max_depth:
                line = getattr(node, "lineno", None)
                if line is not None:
                    summary = "Deeply nested logic"
                    explanation = (
                        f"This code block (starting at line {line}) is nested more than {self.max_depth} levels deep. "
                        f"Deep nesting makes code hard to read and maintain. "
                        f"Consider extracting parts into helper functions or simplifying the logic."
                    )
                    self.issues.append(
                        Issue(
                            issue_type="deep_nesting",
                            line=line,
                            summary=summary,
                            explanation=explanation,
                            severity="info",
                        )
                    )

        super().generic_visit(node)

        if is_control:
            self.current_depth -= 1


class LongFunctionChecker(ast.NodeVisitor):
    """
    Flags functions that are longer than a threshold number of statements.
    """

    def __init__(self, max_statements: int = 20) -> None:
        self.max_statements = max_statements
        self.issues: List[Issue] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Approximate: number of statements in the direct body
        num_statements = len(node.body)
        if num_statements > self.max_statements:
            line = getattr(node, "lineno", None)
            if line is not None:
                summary = "Long function"
                explanation = (
                    f"Function '{node.name}' has {num_statements} top-level statements, "
                    f"which is more than the recommended {self.max_statements}. "
                    f"Long functions are harder to test and understand. "
                    f"Consider splitting it into smaller helper functions with clear responsibilities."
                )
                self.issues.append(
                    Issue(
                        issue_type="long_function",
                        line=line,
                        summary=summary,
                        explanation=explanation,
                        severity="info",
                    )
                )
        self.generic_visit(node)


class VariableUsageVisitor(ast.NodeVisitor):
    """
    Collects assigned and used variables to detect unused ones.
    """

    def __init__(self) -> None:
        self.assigned: Dict[str, List[int]] = {}
        self.used: Set[str] = set()

    # Assignment: a = 1, x, y = ...
    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self._collect_assigned(target)
        self.generic_visit(node)

    # Walrus operator: (Python 3.8+): x := 1
    def visit_NamedExpr(self, node: ast.NamedExpr):
        self._collect_assigned(node.target)
        self.generic_visit(node)

    # Function arguments
    def visit_arg(self, node: ast.arg):
        name = node.arg
        line = getattr(node, "lineno", None)
        if line is not None:
            self.assigned.setdefault(name, []).append(line)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            self.used.add(node.id)
        self.generic_visit(node)

    def _collect_assigned(self, target):
        if isinstance(target, ast.Name):
            name = target.id
            line = getattr(target, "lineno", None)
            if line is not None:
                self.assigned.setdefault(name, []).append(line)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._collect_assigned(elt)


def check_unused_variables(tree: ast.AST) -> List[Issue]:
    visitor = VariableUsageVisitor()
    visitor.visit(tree)

    issues: List[Issue] = []

    for name, lines in visitor.assigned.items():
        # Ignore "throwaway" names like "_" by convention
        if name == "_":
            continue
        if name not in visitor.used:
            first_line = lines[0]
            summary = "Unused variable"
            explanation = (
                f"The variable '{name}' is assigned at line {first_line} but never used afterwards. "
                f"Unused variables can confuse readers and may indicate leftover or incomplete code. "
                f"Consider removing it or using it if it was intended."
            )
            issues.append(
                Issue(
                    issue_type="unused_variable",
                    line=first_line,
                    summary=summary,
                    explanation=explanation,
                    severity="info",
                )
            )

    return issues


# -------------------------
# Entry point for all rules
# -------------------------


def run_all_rules(tree: ast.AST) -> List[Issue]:
    issues: List[Issue] = []

    # 1) Unreachable code
    unreachable_checker = UnreachableCodeChecker()
    issues.extend(unreachable_checker.run(tree))

    # 2) Deep nesting
    nesting_checker = NestingDepthChecker(max_depth=3)
    nesting_checker.visit(tree)
    issues.extend(nesting_checker.issues)

    # 3) Long functions
    long_func_checker = LongFunctionChecker(max_statements=20)
    long_func_checker.visit(tree)
    issues.extend(long_func_checker.issues)

    # 4) Unused variables
    issues.extend(check_unused_variables(tree))

    return issues
