"""Checker for redundant @pytest.mark.usefixtures decorators.

When a module or its parent ``conftest.py`` files set
``pytestmark = pytest.mark.usefixtures("fixture")``, every test in that
module already uses the fixture. Adding
``@pytest.mark.usefixtures("fixture")`` on individual tests is redundant.

Similarly, ``autouse=True`` fixtures in ``conftest.py`` files apply to all
tests automatically, so explicit ``@pytest.mark.usefixtures`` for those
is also redundant.
"""

from pathlib import Path

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module


def _is_pytest_mark_usefixtures(node: nodes.Call) -> bool:
    """Check if a call node is ``pytest.mark.usefixtures(...)``."""
    if not isinstance(node.func, nodes.Attribute):
        return False
    if node.func.attrname != "usefixtures":
        return False
    # Verify the chain is *.mark.usefixtures
    if not isinstance(node.func.expr, nodes.Attribute):
        return False
    return bool(node.func.expr.attrname == "mark")


def _extract_usefixtures_names(node: nodes.NodeNG) -> set[str]:
    """Extract fixture names from a pytest.mark.usefixtures(...) call."""
    if not isinstance(node, nodes.Call):
        return set()
    if not _is_pytest_mark_usefixtures(node):
        return set()
    return {
        arg.value
        for arg in node.args
        if isinstance(arg, nodes.Const) and isinstance(arg.value, str)
    }


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


def _collect_autouse_fixtures(module: nodes.Module) -> set[str]:
    """Collect names of autouse=True fixtures from a module."""
    fixtures: set[str] = set()
    for node in module.body:
        if not isinstance(node, nodes.FunctionDef):
            continue
        if not node.decorators:
            continue
        for decorator in node.decorators.nodes:
            if not isinstance(decorator, nodes.Call):
                continue
            # Check for @pytest.fixture(autouse=True)
            if not isinstance(decorator.func, nodes.Attribute):
                continue
            if decorator.func.attrname != "fixture":
                continue
            for kw in decorator.keywords:
                if kw.arg == "autouse" and isinstance(kw.value, nodes.Const):
                    if kw.value.value is True:
                        fixtures.add(node.name)
                        # Check for name= override
                        for name_kw in decorator.keywords:
                            if name_kw.arg == "name" and isinstance(
                                name_kw.value, nodes.Const
                            ):
                                fixtures.discard(node.name)
                                fixtures.add(name_kw.value.value)
    return fixtures


def _collect_conftest_fixtures(module: nodes.Module) -> set[str]:
    """Collect usefixtures and autouse fixtures from conftest.py files."""
    if not module.file:
        return set()

    fixtures: set[str] = set()
    module_dir = Path(module.file).parent

    # Walk up directories looking for conftest.py files
    # Stop at the tests root (don't go above it)
    current = module_dir
    while current.name and current.name != "tests":
        conftest_path = current / "conftest.py"
        if conftest_path.exists():
            try:
                conftest_module = astroid.MANAGER.ast_from_file(str(conftest_path))
                fixtures.update(_collect_module_usefixtures(conftest_module))
                fixtures.update(_collect_autouse_fixtures(conftest_module))
            except astroid.exceptions.AstroidSyntaxError:
                pass
        current = current.parent

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
            "fixture that is already declared in the module's pytestmark "
            "or in a parent conftest.py (via pytestmark or autouse=True).",
        ),
    }
    options = ()

    _module_fixtures: set[str]

    def visit_module(self, node: nodes.Module) -> None:
        """Collect module-level usefixtures."""
        self._module_fixtures = set()
        if is_test_module(node.name):
            self._module_fixtures = _collect_module_usefixtures(node)
            self._module_fixtures.update(_collect_conftest_fixtures(node))

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
