"""Checker for unused fixture arguments in test functions.

Test functions that receive a fixture argument but never reference it in the
function body should use ``@pytest.mark.usefixtures("name")`` instead. This
keeps the function signature clean and makes it clear the fixture is only
needed for its side effects.

This rule only applies to ``test_*`` functions, not to fixture functions.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module


class UnusedTestFixtureArgsChecker(BaseChecker):
    """Checker for unused fixture arguments in test functions."""

    name = "home_assistant_unused_test_fixture_args"
    priority = -1
    msgs = {
        "R7402": (
            "Argument '%s' is not used in %s, use "
            '`@pytest.mark.usefixtures("%s")` instead',
            "home-assistant-unused-test-fixture-argument",
            "Used when a test function has a fixture argument that is never "
            "referenced in the function body. Use @pytest.mark.usefixtures "
            "to declare the dependency instead.",
        ),
    }
    options = ()

    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in a test module."""
        self._in_test_module = is_test_module(node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check test functions for unused fixture arguments."""
        if not self._in_test_module:
            return

        if not node.name.startswith("test_"):
            return

        # Only check top-level test functions (not nested)
        if not isinstance(node.parent, nodes.Module):
            return

        # Collect all argument names (skip 'self' for methods)
        arg_names = {arg.name for arg in node.args.args if arg.name != "self"}

        if not arg_names:
            return

        # Collect all Name references in the function body
        used_names: set[str] = set()
        for child in node.nodes_of_class(nodes.Name):
            used_names.add(child.name)

        for arg_name in sorted(arg_names - used_names):
            arg_node = next(arg for arg in node.args.args if arg.name == arg_name)
            self.add_message(
                "home-assistant-unused-test-fixture-argument",
                node=arg_node,
                args=(arg_name, node.name, arg_name),
            )

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(UnusedTestFixtureArgsChecker(linter))
