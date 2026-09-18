"""Checker for non-deterministic test execution paths.

``if`` and ``match`` statements inside test functions create non-deterministic
execution paths — some branches may never run, silently hiding failures.
Tests should use ``@pytest.mark.parametrize`` to cover different cases
explicitly, or split into separate test functions.

This rule only applies to ``test_*`` functions in test modules.

To reduce false positives, the checker skips:
- Guard clauses (``return``, ``raise``, ``pytest.skip/fail/xfail``)
- ``if`` statements where the condition references a function parameter
  (conditional setup in an already-parametrized test)
- ``if`` statements that don't contain any ``assert`` in their branches
  (pure setup logic, not branching assertions)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module


def _is_guard_clause(node: nodes.If) -> bool:
    """Return True if the ``if`` is a guard clause.

    Guards are allowed patterns:
    - ``pytest.skip(...)`` / ``pytest.xfail(...)``
    - Early ``return``
    - ``raise`` (e.g., ``pytest.fail`` or assertion helpers)
    """
    for child in node.body:
        if isinstance(child, (nodes.Return, nodes.Raise)):
            return True
        if isinstance(child, nodes.Expr) and isinstance(child.value, nodes.Call):
            call = child.value
            if isinstance(call.func, nodes.Attribute) and call.func.attrname in (
                "skip",
                "xfail",
                "fail",
            ):
                return True
    return False


def _condition_references_parameter(node: nodes.If, param_names: set[str]) -> bool:
    """Return True if the ``if`` condition references a function parameter.

    This catches conditional setup in parametrized tests, e.g.::

        @pytest.mark.parametrize("action_type", ["template", "trigger"])
        def test_something(action_type):
            if action_type == "template":
                action = {...}
            else:
                action = {...}
    """
    for name_node in node.test.nodes_of_class(nodes.Name):
        if name_node.name in param_names:
            return True
    return False


def _contains_assert(node: nodes.NodeNG) -> bool:
    """Return True if the node tree contains any ``assert`` statement."""
    return any(node.nodes_of_class(nodes.Assert))


def _branches_contain_assert(node: nodes.If) -> bool:
    """Return True if any branch of the ``if`` contains an ``assert``."""
    if _contains_assert(node):
        return True
    for handler in node.orelse:
        if isinstance(handler, nodes.If):
            if _branches_contain_assert(handler):
                return True
        elif _contains_assert(handler):
            return True
    return False


class HassTestDeterminismChecker(BaseChecker):
    """Checker for branching in test functions.

    ``if`` and ``match`` statements in test functions create
    non-deterministic execution paths. Use ``@pytest.mark.parametrize``
    or split into separate tests instead.
    """

    name = "home_assistant_test_determinism"
    priority = -1
    msgs = {
        "W7409": (
            "Test function '%s' contains a %s statement, use "
            "`@pytest.mark.parametrize` or split into separate tests instead",
            "home-assistant-test-non-deterministic",
            "Used when a test function contains an if or match statement "
            "that creates non-deterministic execution paths. Use "
            "pytest.mark.parametrize to explicitly cover each case.",
        ),
    }
    options = ()

    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in a test module."""
        self._in_test_module = is_test_module(node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check test functions for branching statements."""
        if not self._in_test_module:
            return

        if not node.name.startswith("test_"):
            return

        # Only check top-level test functions
        if not isinstance(node.parent, nodes.Module):
            return

        param_names = {arg.name for arg in node.args.args}

        for child in node.body:
            if isinstance(child, nodes.If):
                if _is_guard_clause(child):
                    continue
                if _condition_references_parameter(child, param_names):
                    continue
                if not _branches_contain_assert(child):
                    continue
                self.add_message(
                    "home-assistant-test-non-deterministic",
                    node=child,
                    args=(node.name, "if"),
                )
            elif isinstance(child, nodes.Match):
                self.add_message(
                    "home-assistant-test-non-deterministic",
                    node=child,
                    args=(node.name, "match"),
                )

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTestDeterminismChecker(linter))
