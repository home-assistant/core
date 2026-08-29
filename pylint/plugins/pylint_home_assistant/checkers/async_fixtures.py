"""Checker for synchronous fixture loading in async test functions."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

FUNCTION_NAMES = (
    "load_fixture",
    "load_json_array_fixture",
    "load_json_object_fixture",
)


class HassLoadFixturesChecker(BaseChecker):
    """Checker for I/O load fixtures."""

    name = "home_assistant_async_load_fixtures"
    priority = -1
    msgs = {
        "W7404": (
            "Test fixture files should be loaded asynchronously",
            "home-assistant-async-load-fixtures",
            "Used when a test fixture file is loaded synchronously",
        ),
    }
    options = ()

    _decorators_queue: list[nodes.Decorators]
    _function_queue: list[nodes.FunctionDef | nodes.AsyncFunctionDef]
    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Visit a module definition."""
        self._in_test_module = is_test_module(node.name)
        self._decorators_queue = []
        self._function_queue = []

    def visit_decorators(self, node: nodes.Decorators) -> None:
        """Visit a function definition."""
        self._decorators_queue.append(node)

    def leave_decorators(self, node: nodes.Decorators) -> None:
        """Leave a function definition."""
        self._decorators_queue.pop()

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Visit a function definition."""
        self._function_queue.append(node)

    def leave_functiondef(self, node: nodes.FunctionDef) -> None:
        """Leave a function definition."""
        self._function_queue.pop()

    visit_asyncfunctiondef = visit_functiondef
    leave_asyncfunctiondef = leave_functiondef

    def visit_call(self, node: nodes.Call) -> None:
        """Check for sync I/O in load_fixture."""
        if (
            # Ensure we are in a test module
            not self._in_test_module
            # Ensure we are in an async function context
            or not self._function_queue
            or not isinstance(self._function_queue[-1], nodes.AsyncFunctionDef)
            # Ensure we are not in the decorators
            or self._decorators_queue
            # Check function name
            or not isinstance(node.func, nodes.Name)
            or node.func.name not in FUNCTION_NAMES
        ):
            return

        self.add_message("home-assistant-async-load-fixtures", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassLoadFixturesChecker(linter))
