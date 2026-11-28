"""Checker for manually enabled entities in ``snapshot_platform`` tests.

Tests that snapshot a platform with ``snapshot_platform`` should snapshot
every entity, including the ones that are disabled by default. The
``entity_registry_enabled_by_default`` fixture enables all entities before
the integration is set up. Enabling them by hand in the test instead,
with ``entity_registry.async_update_entity(..., disabled_by=None)``
followed by a config entry reload, is more code, slower, and easily misses
entities.

This checker flags ``<registry>.async_update_entity(...)`` calls that pass
``disabled_by=None`` inside a ``test_*`` function that also calls
``snapshot_platform``.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

_SNAPSHOT_PLATFORM = "snapshot_platform"
_UPDATE_ENTITY = "async_update_entity"


def _call_name(node: nodes.Call) -> str | None:
    """Return the called function or method name, if it is a plain name."""
    func = node.func
    name: str | None = None
    if isinstance(func, nodes.Name):
        name = func.name
    elif isinstance(func, nodes.Attribute):
        name = func.attrname
    return name


def _enables_entity(node: nodes.Call) -> bool:
    """Return True when *node* is ``*.async_update_entity(..., disabled_by=None)``."""
    if not isinstance(node.func, nodes.Attribute):
        return False
    if node.func.attrname != _UPDATE_ENTITY:
        return False
    return any(
        keyword.arg == "disabled_by"
        and isinstance(keyword.value, nodes.Const)
        and keyword.value.value is None
        for keyword in node.keywords or ()
    )


class SnapshotEnableEntitiesChecker(BaseChecker):
    """Checker that enforces the enabled-by-default fixture for snapshots."""

    name = "home_assistant_tests_snapshot_enable_entities"
    priority = -1
    msgs = {
        "R7406": (
            "Use the 'entity_registry_enabled_by_default' fixture instead of "
            "enabling entities manually before 'snapshot_platform'",
            "home-assistant-tests-snapshot-enable-entities",
            "Used when a test that calls ``snapshot_platform`` enables "
            "entities by calling ``async_update_entity(..., "
            "disabled_by=None)``. Add "
            '``@pytest.mark.usefixtures("entity_registry_enabled_by_default")`` '
            "to the test instead, so all entities are enabled before the "
            "integration is set up.",
        ),
    }
    options = ()

    _active: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Only check test modules."""
        self._active = is_test_module(node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check a test function."""
        if not self._active or not node.name.startswith("test_"):
            return
        # Nested functions are covered by the walk of their test function.
        if not isinstance(node.parent, (nodes.Module, nodes.ClassDef)):
            return

        calls = list(node.nodes_of_class(nodes.Call))
        if not any(_call_name(call) == _SNAPSHOT_PLATFORM for call in calls):
            return

        for call in calls:
            if _enables_entity(call):
                self.add_message(
                    "home-assistant-tests-snapshot-enable-entities", node=call
                )

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(SnapshotEnableEntitiesChecker(linter))
