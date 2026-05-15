"""Checker for redundant @pytest.mark.usefixtures decorators.

When a module sets ``pytestmark = pytest.mark.usefixtures("fixture")``,
every test in that module already uses the fixture. Adding
``@pytest.mark.usefixtures("fixture")`` on individual tests is redundant.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module


def _extract_usefixtures_names(node: nodes.NodeNG) -> set[str]:
    """Extract fixture names from a pytest.mark.usefixtures(...) call."""
    names: set[str] = set()
    if not isinstance(node, nodes.Call):
        return names
    if not isinstance(node.func, nodes.Attribute):
        return names
    if node.func.attrname != "usefixtures":
        return names
    for arg in node.args:
        if isinstance(arg, nodes.Const) and isinstance(arg.value, str):
            names.add(arg.value)
    return names


def _collect_module_usefixtures(module: nodes.Module) -> set[str]:
    """Collect fixture names from module-level pytestmark assignments."""
    fixtures: set[str] = set()
    for node in module.body:
        if not isinstance(node, (nodes.Assign, nodes.AnnAssign)):
            continue

        # Get the target name
        if isinstance(node, nodes.Assign):
            targets = node.targets
        else:
            targets = [node.target]

        for target in targets:
            if not isinstance(target, nodes.AssignName):
                continue
            if target.name != "pytestmark":
                continue

            value = node.value
            if value is None:
                continue

            # Reassignment replaces the previous value
            fixtures.clear()

            # pytestmark = pytest.mark.usefixtures("a", "b")
            if isinstance(value, nodes.Call):
                fixtures.update(_extract_usefixtures_names(value))

            # pytestmark = [pytest.mark.usefixtures("a"), ...]
            elif isinstance(value, (nodes.List, nodes.Tuple)):
                for elt in value.elts:
                    fixtures.update(_extract_usefixtures_names(elt))

    return fixtures


class RedundantUsefixtures(BaseChecker):
    """Checker for redundant @pytest.mark.usefixtures on test functions."""

    name = "home_assistant_tests_redundant_usefixtures"
    priority = -1
    msgs = {
        "R7403": (
            "'%s' is already applied by `pytestmark` at module level, "
            "the `@pytest.mark.usefixtures` decorator is redundant",
            "home-assistant-tests-redundant-usefixtures",
            "Used when a test function has @pytest.mark.usefixtures for a "
            "fixture that is already declared in the module's pytestmark.",
        ),
    }
    options = ()

    _module_fixtures: set[str]

    def visit_module(self, node: nodes.Module) -> None:
        """Collect module-level usefixtures."""
        self._module_fixtures = set()
        if is_test_module(node.name):
            self._module_fixtures = _collect_module_usefixtures(node)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check test functions for redundant usefixtures decorators."""
        if not self._module_fixtures:
            return

        if not node.name.startswith("test_"):
            return

        if not node.decorators:
            return

        for decorator in node.decorators.nodes:
            per_test = _extract_usefixtures_names(decorator)
            for name in per_test & self._module_fixtures:
                self.add_message(
                    "home-assistant-tests-redundant-usefixtures",
                    node=decorator,
                    args=(name,),
                )

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(RedundantUsefixtures(linter))
