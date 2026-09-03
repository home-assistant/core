"""Checker for direct calls to ``async_migrate_entry`` from tests.

Tests should not invoke an integration's ``async_migrate_entry``
directly. Instead, tests should let Home Assistant trigger the
migration as part of the normal setup pipeline via
``await hass.config_entries.async_setup(entry.entry_id)`` so that the
real migration flow (version updates, reloads, etc.) is exercised.

This checker flags any ``await <domain>.async_migrate_entry(...)``
or ``await async_migrate_entry(...)`` call in a test module whose
target resolves to a function defined in an integration's ``__init__``
module under ``homeassistant.components.*``.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module, parse_module


def _is_integration_async_migrate_entry(call: nodes.Call) -> bool:
    """Return True if *call* targets an integration's ``async_migrate_entry``."""
    func = call.func
    match func:
        case nodes.Attribute(attrname="async_migrate_entry"):
            pass
        case nodes.Name(name="async_migrate_entry"):
            pass
        case _:
            return False

    try:
        inferred_values = list(func.infer())
    except astroid.InferenceError, astroid.AstroidError:
        return False

    seen_qnames: set[str] = set()
    for inferred in inferred_values:
        if inferred is astroid.Uninferable:
            continue
        if not isinstance(inferred, (nodes.FunctionDef, nodes.AsyncFunctionDef)):
            continue
        qname = inferred.qname()
        if not qname or qname in seen_qnames:
            continue
        seen_qnames.add(qname)
        # qname is the function's fully-qualified name, e.g.
        # ``homeassistant.components.sun.async_migrate_entry``. Strip the
        # function name to get the module and parse it.
        module_qname = qname.rsplit(".", 1)[0]
        parsed = parse_module(module_qname)
        if parsed is None:
            continue
        # ``async_migrate_entry`` lives in the integration's ``__init__``.
        if parsed.module is None:
            return True
    return False


class DirectAsyncMigrateEntry(BaseChecker):
    """Checker for direct calls to async_migrate_entry in tests."""

    name = "home_assistant_tests_direct_async_migrate_entry"
    priority = -1
    msgs = {
        "W7421": (
            "Do not call `async_migrate_entry` directly from tests; use "
            "`await hass.config_entries.async_setup(entry.entry_id)` instead",
            "home-assistant-tests-direct-async-migrate-entry",
            "Used when a test module calls an integration's "
            "`async_migrate_entry` directly. Tests should let Home Assistant "
            "drive the setup so the migration flow is exercised through the "
            "normal pipeline.",
        ),
    }
    options = ()

    _in_test_module: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Record whether the current module is a test module."""
        self._in_test_module = is_test_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Flag direct calls to an integration's async_migrate_entry."""
        if not self._in_test_module:
            return
        if _is_integration_async_migrate_entry(node):
            self.add_message(
                "home-assistant-tests-direct-async-migrate-entry",
                node=node,
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DirectAsyncMigrateEntry(linter))
