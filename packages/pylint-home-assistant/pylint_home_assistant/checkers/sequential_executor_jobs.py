"""Checker for sequential executor job calls.

Multiple sequential ``await hass.async_add_executor_job()`` calls should
be grouped into a single executor job to avoid unnecessary context switches
back to the event loop between blocking calls.

https://contributors.home-assistant.io/core/internals/asyncio/#move-blocking-work-to-the-executor
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

_DEFAULT_EXECUTOR = "default"

_EXECUTOR_JOB_STATEMENTS = (
    nodes.Assign,
    nodes.AnnAssign,
    nodes.AugAssign,
    nodes.Expr,
    nodes.Return,
)

# Statements that do not yield to the event loop when they contain no await
_TRANSPARENT_STATEMENTS = (
    nodes.Assign,
    nodes.AnnAssign,
    nodes.AugAssign,
    nodes.Expr,
    nodes.Assert,
    nodes.Delete,
    nodes.Pass,
)

_NEW_SCOPE_NODES = (
    nodes.FunctionDef,
    nodes.AsyncFunctionDef,
    nodes.Lambda,
    nodes.ClassDef,
)


def _is_hass_receiver(node: nodes.NodeNG) -> bool:
    """Return True if *node* is ``hass``, ``self.hass`` or ``self._hass``."""
    if isinstance(node, nodes.Name):
        return bool(node.name == "hass")
    return isinstance(node, nodes.Attribute) and node.attrname in {"hass", "_hass"}


def _executor_key(call: nodes.Call) -> str | None:
    """Return the executor *call* submits work to, or None if not an executor job.

    Jobs submitted to different executors must not be grouped, so the
    returned key identifies the executor.
    """
    func = call.func
    if isinstance(func, nodes.Name):
        return _DEFAULT_EXECUTOR if func.name == "to_thread" else None
    if not isinstance(func, nodes.Attribute):
        return None
    if func.attrname == "async_add_executor_job":
        if _is_hass_receiver(func.expr):
            return _DEFAULT_EXECUTOR
        return str(func.expr.as_string())
    if func.attrname == "async_add_import_executor_job":
        return f"import:{func.expr.as_string()}"
    if func.attrname == "run_in_executor":
        if not call.args:
            return None
        executor = call.args[0]
        if isinstance(executor, nodes.Const) and executor.value is None:
            return _DEFAULT_EXECUTOR
        return str(executor.as_string())
    if (
        func.attrname == "to_thread"
        and isinstance(func.expr, nodes.Name)
        and func.expr.name == "asyncio"
    ):
        return _DEFAULT_EXECUTOR
    return None


def _awaits(node: nodes.NodeNG) -> list[nodes.Await]:
    """Return the awaits in *node* that run in the current scope."""
    found: list[nodes.Await] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, nodes.Await):
            found.append(current)
        stack.extend(
            child
            for child in current.get_children()
            if not isinstance(child, _NEW_SCOPE_NODES)
        )
    return found


def _executor_job_key(node: nodes.NodeNG) -> str | None:
    """Return the executor key if *node* only awaits a single executor job."""
    if not isinstance(node, _EXECUTOR_JOB_STATEMENTS):
        return None
    awaits = _awaits(node)
    if len(awaits) != 1 or not isinstance(call := awaits[0].value, nodes.Call):
        return None
    return _executor_key(call)


def _calls_async_api(node: nodes.NodeNG) -> bool:
    """Return True if *node* calls a function named ``async_*``.

    Such functions must run in the event loop, so they cannot be moved
    into an executor job together with the surrounding blocking calls.
    """
    for call in node.nodes_of_class(nodes.Call, skip_klass=_NEW_SCOPE_NODES):
        func = call.func
        name = func.attrname if isinstance(func, nodes.Attribute) else None
        if isinstance(func, nodes.Name):
            name = func.name
        if name is not None and name.startswith("async_"):
            return True
    return False


def _is_transparent(node: nodes.NodeNG) -> bool:
    """Return True if *node* can move into an executor job with its neighbors."""
    return (
        isinstance(node, _TRANSPARENT_STATEMENTS)
        and not _awaits(node)
        and not _calls_async_api(node)
    )


class SequentialExecutorJobsChecker(BaseChecker):
    """Checker for sequential executor job calls."""

    name = "home_assistant_sequential_executor_jobs"
    priority = -1
    msgs = {
        "W7415": (
            "Sequential `async_add_executor_job` calls should be grouped "
            "into a single executor job",
            "home-assistant-sequential-executor-jobs",
            "Used when multiple awaited executor jobs (such as "
            "hass.async_add_executor_job()) run in sequence without yielding "
            "to the event loop in between. Group the blocking operations into "
            "a single function and call async_add_executor_job once.",
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check for sequential executor job calls."""
        if not self._in_integration:
            return

        self._check_body(node.body)

    visit_asyncfunctiondef = visit_functiondef

    def _check_body(self, body: list[nodes.NodeNG]) -> None:
        """Check a list of statements for sequential executor job calls."""
        prev_executor: str | None = None

        for stmt in body:
            if (executor := _executor_job_key(stmt)) is not None:
                if executor == prev_executor:
                    self.add_message(
                        "home-assistant-sequential-executor-jobs",
                        node=stmt,
                    )
                prev_executor = executor
                continue

            if not _is_transparent(stmt):
                prev_executor = None

            # Recurse into control flow blocks (but not nested functions)
            if isinstance(stmt, nodes.If):
                self._check_body(stmt.body)
                self._check_body(stmt.orelse)
            elif isinstance(stmt, (nodes.Try, nodes.TryStar)):
                self._check_body(stmt.body)
                for handler in stmt.handlers:
                    self._check_body(handler.body)
                self._check_body(stmt.orelse)
                self._check_body(stmt.finalbody)
            elif isinstance(stmt, (nodes.With, nodes.AsyncWith)):
                self._check_body(stmt.body)
            elif isinstance(stmt, (nodes.For, nodes.AsyncFor, nodes.While)):
                self._check_body(stmt.body)
                self._check_body(stmt.orelse)
            elif isinstance(stmt, nodes.Match):
                for case in stmt.cases:
                    self._check_body(case.body)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(SequentialExecutorJobsChecker(linter))
