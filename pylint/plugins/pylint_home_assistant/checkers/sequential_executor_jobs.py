"""Checker for sequential async_add_executor_job calls.

Multiple sequential ``await hass.async_add_executor_job()`` calls should
be grouped into a single executor job to avoid unnecessary context switches
back to the event loop between blocking calls.

https://developers.home-assistant.io/docs/asyncio_working_with_async/#calling-sync-functions-from-async
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module


def _executor_await(node: nodes.NodeNG) -> nodes.Await | None:
    """Return the ``await *.async_add_executor_job(...)`` node, if any."""
    if not isinstance(node, (nodes.Assign, nodes.AnnAssign, nodes.Expr, nodes.Return)):
        return None

    value = node.value
    if not isinstance(value, nodes.Await):
        return None

    call = value.value
    if not isinstance(call, nodes.Call):
        return None

    if (
        isinstance(call.func, nodes.Attribute)
        and call.func.attrname == "async_add_executor_job"
    ):
        return value
    return None


def _is_executor_job_await(node: nodes.NodeNG) -> bool:
    """Return True if *node* is ``await *.async_add_executor_job(...)``."""
    return _executor_await(node) is not None


def _has_non_executor_await(body: list[nodes.NodeNG]) -> bool:
    """Return True if *body* contains an await that is not an executor job.

    Nested functions are skipped: their awaits belong to a different
    execution context and don't prevent hoisting an executor job.
    """
    for stmt in body:
        executor_awaits = {
            executor
            for sub in stmt.nodes_of_class(
                (nodes.Assign, nodes.AnnAssign, nodes.Expr, nodes.Return),
                skip_klass=(nodes.FunctionDef, nodes.AsyncFunctionDef),
            )
            if (executor := _executor_await(sub)) is not None
        }
        for await_node in stmt.nodes_of_class(
            nodes.Await, skip_klass=(nodes.FunctionDef, nodes.AsyncFunctionDef)
        ):
            if await_node not in executor_awaits:
                return True
    return False


class SequentialExecutorJobsChecker(BaseChecker):
    """Checker for sequential async_add_executor_job calls."""

    name = "home_assistant_sequential_executor_jobs"
    priority = -1
    msgs = {
        "W7415": (
            "Sequential `async_add_executor_job` calls should be grouped "
            "into a single executor job",
            "home-assistant-sequential-executor-jobs",
            "Used when multiple await hass.async_add_executor_job() calls "
            "appear in sequence. Group the blocking operations into a "
            "single function and call async_add_executor_job once.",
        ),
        "W7434": (
            "`async_add_executor_job` call inside a loop should be grouped "
            "into a single executor job",
            "home-assistant-executor-job-in-loop",
            "Used when an await hass.async_add_executor_job() call appears "
            "inside a loop body. Move the loop into a single function and "
            "call async_add_executor_job once.",
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

    def _check_body(self, body: list[nodes.NodeNG], in_loop: bool = False) -> None:
        """Check a list of statements for sequential executor job calls."""
        prev_was_executor = False

        for stmt in body:
            if _is_executor_job_await(stmt):
                if prev_was_executor:
                    self.add_message(
                        "home-assistant-sequential-executor-jobs",
                        node=stmt,
                    )
                elif in_loop:
                    self.add_message(
                        "home-assistant-executor-job-in-loop",
                        node=stmt,
                    )
                prev_was_executor = True
            else:
                prev_was_executor = False

                # Recurse into control flow blocks (but not nested functions)
                if isinstance(stmt, nodes.If):
                    self._check_body(stmt.body, in_loop)
                    self._check_body(stmt.orelse, in_loop)
                elif isinstance(stmt, nodes.Try):
                    self._check_body(stmt.body, in_loop)
                    for handler in stmt.handlers:
                        self._check_body(handler.body, in_loop)
                    self._check_body(stmt.orelse, in_loop)
                    self._check_body(stmt.finalbody, in_loop)
                elif isinstance(
                    stmt,
                    (
                        nodes.With,
                        nodes.AsyncWith,
                    ),
                ):
                    self._check_body(stmt.body, in_loop)
                elif isinstance(
                    stmt,
                    (
                        nodes.For,
                        nodes.AsyncFor,
                        nodes.While,
                    ),
                ):
                    # Only flag executor jobs in a loop when the loop has no
                    # other awaited async work; otherwise the blocking calls
                    # cannot be hoisted into a single executor job.
                    loop_in_loop = not _has_non_executor_await(stmt.body)
                    self._check_body(stmt.body, in_loop=loop_in_loop)
                    self._check_body(stmt.orelse, in_loop)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(SequentialExecutorJobsChecker(linter))
