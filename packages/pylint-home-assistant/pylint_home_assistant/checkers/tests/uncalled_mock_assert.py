"""Checker for mock assertion methods that are asserted instead of called.

``assert mock.assert_called_once`` accesses the bound method without calling
it. A bound method is always truthy, so the assertion always passes and the
mock is never checked. The method has to be called instead:
``mock.assert_called_once()``.
"""

from collections.abc import Iterator

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

_MOCK_ASSERT_METHODS = frozenset(
    {
        "assert_any_await",
        "assert_any_call",
        "assert_awaited",
        "assert_awaited_once",
        "assert_awaited_once_with",
        "assert_awaited_with",
        "assert_called",
        "assert_called_once",
        "assert_called_once_with",
        "assert_called_with",
        "assert_has_awaits",
        "assert_has_calls",
        "assert_not_awaited",
        "assert_not_called",
    }
)


def _uncalled_mock_asserts(node: nodes.NodeNG) -> Iterator[nodes.Attribute]:
    """Yield the mock assertion methods *node* tests for truthiness."""
    if isinstance(node, nodes.UnaryOp) and node.op == "not":
        yield from _uncalled_mock_asserts(node.operand)
    elif isinstance(node, nodes.BoolOp):
        for value in node.values:
            yield from _uncalled_mock_asserts(value)
    elif isinstance(node, nodes.Attribute) and node.attrname in _MOCK_ASSERT_METHODS:
        yield node


class UncalledMockAssert(BaseChecker):
    """Checker for mock assertion methods that are asserted instead of called."""

    name = "home_assistant_tests_uncalled_mock_assert"
    priority = -1
    msgs = {
        "W7462": (
            "Mock assertion method `%s` is accessed but not called",
            "home-assistant-tests-uncalled-mock-assert",
            (
                "Used when a test asserts a mock assertion method, such as "
                "`assert mock.assert_called_once`, instead of calling it. A "
                "bound method is always truthy, so the assertion always "
                "passes and the mock is never checked."
            ),
        ),
    }
    options = ()

    _in_test_module: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Record whether the current module is a test module."""
        self._in_test_module = is_test_module(node.name)

    def visit_assert(self, node: nodes.Assert) -> None:
        """Flag mock assertion methods that are asserted instead of called."""
        if not self._in_test_module:
            return

        for attribute in _uncalled_mock_asserts(node.test):
            self.add_message(
                "home-assistant-tests-uncalled-mock-assert",
                node=attribute,
                args=(attribute.attrname,),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(UncalledMockAssert(linter))
