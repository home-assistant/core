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


def _is_executor_job_await(node: nodes.NodeNG) -> bool:
    """Return True if *node* is ``await *.async_add_executor_job(...)``."""
    if not isinstance(node, (nodes.Assign, nodes.AnnAssign, nodes.Expr, nodes.Return)):
        return False

    value = node.value
    if value is None:
        return False

    # Must be an Await
    if not isinstance(value, nodes.Await):
        return False

    call = value.value
    if not isinstance(call, nodes.Call):
        return False

    return (
        isinstance(call.func, nodes.Attribute)
        and call.func.attrname == "async_add_executor_job"
    )


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
        prev_was_executor = False

        for stmt in body:
            if _is_executor_job_await(stmt):
                if prev_was_executor:
                    self.add_message(
                        "home-assistant-sequential-executor-jobs",
                        node=stmt,
                    )
                prev_was_executor = True
            else:
                prev_was_executor = False

                # Recurse into control flow blocks (but not nested functions)
                if isinstance(stmt, nodes.If):
                    self._check_body(stmt.body)
                    self._check_body(stmt.orelse)
                elif isinstance(stmt, nodes.Try):
                    self._check_body(stmt.body)
                    for handler in stmt.handlers:
                        self._check_body(handler.body)
                    self._check_body(stmt.orelse)
                    self._check_body(stmt.finalbody)
                elif isinstance(
                    stmt,
                    (
                        nodes.With,
                        nodes.AsyncWith,
                    ),
                ):
                    self._check_body(stmt.body)
                elif isinstance(
                    stmt,
                    (
                        nodes.For,
                        nodes.AsyncFor,
                        nodes.While,
                    ),
                ):
                    self._check_body(stmt.body)
                    self._check_body(stmt.orelse)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(SequentialExecutorJobsChecker(linter))
