"""Checker for direct registry ``async_get`` calls in tests.

Test functions and pytest fixtures should use the standard registry
fixtures defined in ``tests/conftest.py``
(``area_registry``, ``category_registry``, ``device_registry``,
``entity_registry``, ``floor_registry``, ``issue_registry``,
``label_registry``) instead of calling ``<registry>.async_get(hass)``
directly.

This checker flags calls of the form ``<alias>.async_get(...)`` where
``<alias>`` resolves (via a module-level ``from homeassistant.helpers
import ...`` statement) to one of the seven registry helper modules,
when the call is located inside a ``test_*`` function or a
``@pytest.fixture``-decorated function.

Files literally named ``conftest.py`` are exempt — these are where the
registry fixtures themselves are typically defined.
"""

from pathlib import Path

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

_REGISTRY_HELPERS: frozenset[str] = frozenset(
    {
        "area_registry",
        "category_registry",
        "device_registry",
        "entity_registry",
        "floor_registry",
        "issue_registry",
        "label_registry",
    }
)


def _build_alias_map(module: nodes.Module) -> dict[str, str]:
    """Map module-level alias -> registry helper module name.

    Walks top-level ``from homeassistant.helpers import ...`` statements
    and records each imported registry helper, keyed by its alias (or
    its own name when no alias is provided).
    """
    alias_map: dict[str, str] = {}
    for node in module.body:
        if not isinstance(node, nodes.ImportFrom):
            continue
        if node.modname != "homeassistant.helpers":
            continue
        for name, asname in node.names:
            if name not in _REGISTRY_HELPERS:
                continue
            alias_map[asname or name] = name
    return alias_map


def _binds_to_import(name_node: nodes.Name) -> bool:
    """Return True when *name_node* resolves to a module-level import.

    Uses Astroid scope lookup to find the binding for the name at the call
    site. Returns True only when every binding is an ``ImportFrom`` (i.e.
    the name was not shadowed by a parameter, assignment, or other local
    definition such as a fixture instance).
    """
    try:
        _, assignments = name_node.lookup(name_node.name)
    except Exception:  # noqa: BLE001 - defensive: lookup can raise on odd ASTs
        return False
    if not assignments:
        return False
    return all(isinstance(assignment, nodes.ImportFrom) for assignment in assignments)


def _in_test_or_fixture(node: nodes.NodeNG) -> bool:
    """Return True when *node* executes inside a test or pytest fixture.

    Walks the full ancestor chain so calls in nested helpers/callbacks
    defined inside a ``test_*`` function or a ``@pytest.fixture`` function
    are recognized, not just those in the nearest enclosing function.
    """
    parent = node.parent
    while parent is not None and not isinstance(parent, nodes.Module):
        if isinstance(parent, (nodes.FunctionDef, nodes.AsyncFunctionDef)) and (
            parent.name.startswith("test_") or _is_pytest_fixture(parent)
        ):
            return True
        parent = parent.parent
    return False


def _is_pytest_fixture(
    func: nodes.FunctionDef | nodes.AsyncFunctionDef,
) -> bool:
    """Return True when *func* is decorated with ``@pytest.fixture``."""
    if not func.decorators:
        return False
    for decorator in func.decorators.nodes:
        # ``@pytest.fixture(...)`` — a Call whose func is an Attribute
        target = decorator.func if isinstance(decorator, nodes.Call) else decorator
        if not isinstance(target, nodes.Attribute):
            continue
        if target.attrname != "fixture":
            continue
        expr = target.expr
        if isinstance(expr, nodes.Name) and expr.name == "pytest":
            return True
    return False


class RegistryFixturesChecker(BaseChecker):
    """Checker that enforces use of registry fixtures in tests."""

    name = "home_assistant_tests_registry_fixtures"
    priority = -1
    msgs = {
        "R7404": (
            "Use the '%s' fixture instead of calling '%s.async_get(...)' "
            "directly in tests",
            "home-assistant-tests-registry-fixtures",
            "Used when a test function or pytest fixture calls "
            "``<registry>.async_get(hass)`` directly instead of relying "
            "on the corresponding registry fixture defined in "
            "``tests/conftest.py``.",
        ),
    }
    options = ()

    _active: bool
    _alias_map: dict[str, str]

    def visit_module(self, node: nodes.Module) -> None:
        """Record module state and build the alias map."""
        self._active = False
        self._alias_map = {}
        if not is_test_module(node.name):
            return
        # ``tests.helpers`` tests cover the registry helpers themselves and
        # are expected to call ``async_get`` directly.
        if node.name == "tests.helpers" or node.name.startswith("tests.helpers."):
            return
        # Exempt ``conftest.py`` files entirely — registry fixtures live there.
        if node.file and Path(node.file).name == "conftest.py":
            return
        self._active = True
        self._alias_map = _build_alias_map(node)

    def visit_call(self, node: nodes.Call) -> None:
        """Flag direct registry ``async_get`` calls inside tests/fixtures."""
        if not self._active or not self._alias_map:
            return

        func = node.func
        if not isinstance(func, nodes.Attribute):
            return
        if func.attrname != "async_get":
            return
        if not isinstance(func.expr, nodes.Name):
            return

        helper = self._alias_map.get(func.expr.name)
        if helper is None:
            return

        # The alias map only records the module-level spelling. A parameter
        # or local (e.g. the ``entity_registry`` fixture instance) can shadow
        # a non-aliased import, so confirm the name still binds to the
        # recorded ``from homeassistant.helpers import ...`` statement before
        # flagging.
        if not _binds_to_import(func.expr):
            return

        if _in_test_or_fixture(node):
            self.add_message(
                "home-assistant-tests-registry-fixtures",
                node=node,
                args=(helper, helper),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(RegistryFixturesChecker(linter))
