"""Plugin for forbidding direct calls to integration entry-point functions in tests.

Tests should not call ``async_setup``, ``async_setup_entry``,
``async_unload_entry`` or ``async_migrate_entry`` from a component directly.
Instead, they should go through ``hass.config_entries.async_setup``,
``async_unload`` or ``async_migrate``, ``async_setup_component``, or the
integration's ``setup_integration`` test helper.

``async_setup`` is only flagged when imported from the integration's
``__init__.py`` (``homeassistant.components.<integration>``), since platforms
have their own unrelated ``async_setup`` callbacks.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

# Functions flagged regardless of whether they come from __init__.py or a
# platform submodule.
ENTRY_FUNCTION_NAMES: frozenset[str] = frozenset(
    {
        "async_setup_entry",
        "async_unload_entry",
        "async_migrate_entry",
    }
)

# Functions only flagged when they come from the integration's __init__.py
# (``homeassistant.components.<integration>``), not a submodule.
INIT_ONLY_FUNCTION_NAMES: frozenset[str] = frozenset({"async_setup"})

ALL_FUNCTION_NAMES: frozenset[str] = ENTRY_FUNCTION_NAMES | INIT_ONLY_FUNCTION_NAMES

_COMPONENTS_PREFIX = "homeassistant.components."


def _is_init_module(module_path: str) -> bool:
    """Return True if module_path is an integration's __init__.py module.

    That is, ``homeassistant.components.<integration>`` with no further
    submodule segment.
    """
    if not module_path.startswith(_COMPONENTS_PREFIX):
        return False
    remainder = module_path[len(_COMPONENTS_PREFIX) :]
    return bool(remainder) and "." not in remainder


def _is_function_flaggable(name: str, module_path: str) -> bool:
    """Return True if a call to ``name`` from ``module_path`` should be flagged."""
    if name in ENTRY_FUNCTION_NAMES:
        return True
    if name in INIT_ONLY_FUNCTION_NAMES:
        return _is_init_module(module_path)
    return False


class HassNoDirectInitCallsInTestsChecker(BaseChecker):
    """Checker for direct calls to entry-point functions in tests."""

    name = "hass_no_direct_init_calls_in_tests"
    priority = -1
    msgs = {
        "W7483": (
            "Do not call %s directly in tests; use hass.config_entries instead",
            "hass-no-direct-init-calls-in-tests",
            "Used when a test calls async_setup, async_setup_entry, "
            "async_unload_entry or async_migrate_entry from an integration "
            "directly. Tests should go through hass.config_entries.async_setup "
            "/ async_unload / async_migrate, async_setup_component, or the "
            "integration's setup_integration helper. ``async_setup`` is only "
            "flagged when imported from the integration's __init__.py.",
        ),
    }
    options = ()

    _in_test_module: bool
    # alias name -> module dotted path (only for modules under
    # homeassistant.components.<integration>[.submodule])
    _module_aliases: dict[str, str]
    # local name -> (original function name, source module path)
    _direct_names: dict[str, tuple[str, str]]

    def visit_module(self, node: nodes.Module) -> None:
        """Visit a module definition."""
        self._in_test_module = node.name.startswith("tests.components.")
        self._module_aliases = {}
        self._direct_names = {}

    def visit_import(self, node: nodes.Import) -> None:
        """Track ``import homeassistant.components.foo[.sub] [as alias]``."""
        if not self._in_test_module:
            return
        for name, alias in node.names:
            if not name.startswith(_COMPONENTS_PREFIX):
                continue
            # Skip the bare 'homeassistant.components' itself (no integration).
            if name == _COMPONENTS_PREFIX[:-1]:
                continue
            # ``import homeassistant.components.foo`` binds ``homeassistant``
            # locally; we cannot reasonably resolve attribute chains from it
            # here without more work, so only track aliased imports.
            if alias is not None:
                self._module_aliases[alias] = name

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
        """Track ``from homeassistant.components[.foo[.sub]] import ...``."""
        if not self._in_test_module or node.modname is None:
            return

        modname = node.modname
        if modname == _COMPONENTS_PREFIX[:-1]:
            # from homeassistant.components import foo[, bar]
            for name, alias in node.names:
                local = alias or name
                self._module_aliases[local] = f"{modname}.{name}"
            return

        if not modname.startswith(_COMPONENTS_PREFIX):
            return

        # from homeassistant.components.foo[.sub] import <name>[, ...]
        for name, alias in node.names:
            local = alias or name
            if name in ALL_FUNCTION_NAMES:
                self._direct_names[local] = (name, modname)
            else:
                # Could be a submodule import like
                # ``from homeassistant.components.foo import sensor``.
                self._module_aliases[local] = f"{modname}.{name}"

    def visit_call(self, node: nodes.Call) -> None:
        """Check call against the tracked imports."""
        if not self._in_test_module:
            return

        func = node.func

        # Pattern: bare name call -> async_setup_entry(...)
        if isinstance(func, nodes.Name):
            entry = self._direct_names.get(func.name)
            if entry is None:
                return
            original, source_module = entry
            if _is_function_flaggable(original, source_module):
                self.add_message(
                    "hass-no-direct-init-calls-in-tests",
                    node=node,
                    args=(original,),
                )
            return

        # Pattern: attribute call -> something.async_setup_entry(...)
        if isinstance(func, nodes.Attribute):
            if func.attrname not in ALL_FUNCTION_NAMES:
                return

            dotted = _attribute_dotted_path(func.expr)
            if dotted is None:
                return

            # Resolve via tracked aliases first.
            head, _, tail = dotted.partition(".")
            resolved_module: str | None = None
            if head in self._module_aliases:
                base = self._module_aliases[head]
                resolved_module = f"{base}.{tail}" if tail else base
            elif dotted.startswith(_COMPONENTS_PREFIX):
                resolved_module = dotted

            if resolved_module is None:
                return

            if not _is_function_flaggable(func.attrname, resolved_module):
                return

            self.add_message(
                "hass-no-direct-init-calls-in-tests",
                node=node,
                args=(func.attrname,),
            )


def _attribute_dotted_path(node: nodes.NodeNG) -> str | None:
    """Return the dotted path of an attribute/name expression, or None."""
    parts: list[str] = []
    current: nodes.NodeNG | None = node
    while isinstance(current, nodes.Attribute):
        parts.append(current.attrname)
        current = current.expr
    if not isinstance(current, nodes.Name):
        return None
    parts.append(current.name)
    return ".".join(reversed(parts))


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassNoDirectInitCallsInTestsChecker(linter))
