"""Checker for direct calls to ``async_setup_entry`` from tests.

Tests should not invoke an integration's ``async_setup_entry`` directly
(either the one in ``__init__.py`` or in an entity-platform module).
Instead, tests should let Home Assistant perform the setup via
``await hass.config_entries.async_setup(entry.entry_id)`` so that the
real setup pipeline (platforms, services, listeners, unload handlers,
etc.) is exercised.

This checker flags any ``await <something>.async_setup_entry(...)`` or
``await async_setup_entry(...)`` call in a test module whose target
resolves to a function defined under ``homeassistant.components.*``.
The integration-init case and the entity-platform case get separate
messages so violations can be tracked and fixed independently.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module, parse_module


def _resolve_integration_async_setup_entry(call: nodes.Call) -> str | None:
    """Return the kind of integration ``async_setup_entry`` *call* targets.

    Returns ``"init"`` if the target is in the integration's ``__init__``
    module, ``"platform"`` if it is in an entity-platform module, or
    ``None`` if the call does not resolve to an integration's
    ``async_setup_entry``.
    """
    func = call.func
    if isinstance(func, nodes.Attribute):
        if func.attrname != "async_setup_entry":
            return None
    elif isinstance(func, nodes.Name):
        if func.name != "async_setup_entry":
            return None
    else:
        return None

    try:
        inferred_values = list(func.infer())
    except astroid.InferenceError, astroid.AstroidError:
        return None

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
        # ``homeassistant.components.sun.async_setup_entry``. Strip the
        # function name to get the module and parse it.
        module_qname = qname.rsplit(".", 1)[0]
        parsed = parse_module(module_qname)
        if parsed is None:
            continue
        return "init" if parsed.module is None else "platform"
    return None


class DirectAsyncSetupEntry(BaseChecker):
    """Checker for direct calls to async_setup_entry in tests."""

    name = "home_assistant_tests_direct_async_setup_entry"
    priority = -1
    msgs = {
        "W7418": (
            "Do not call `async_setup_entry` directly from tests; use "
            "`await hass.config_entries.async_setup(entry.entry_id)` instead",
            "home-assistant-tests-direct-async-setup-entry",
            "Used when a test module calls an integration's "
            "`async_setup_entry` from `__init__.py` directly. Tests should "
            "let Home Assistant drive the setup so the full setup pipeline "
            "is exercised.",
        ),
        "W7420": (
            "Do not call a platform's `async_setup_entry` directly from "
            "tests; use `await hass.config_entries.async_setup(entry.entry_id)`"
            " instead",
            "home-assistant-tests-direct-platform-async-setup-entry",
            "Used when a test module calls an integration entity platform's "
            "`async_setup_entry` directly. Tests should let Home Assistant "
            "drive the setup so the full setup pipeline is exercised.",
        ),
    }
    options = ()

    _in_test_module: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Record whether the current module is a test module."""
        self._in_test_module = is_test_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Flag direct calls to an integration's async_setup_entry."""
        if not self._in_test_module:
            return
        kind = _resolve_integration_async_setup_entry(node)
        if kind == "init":
            self.add_message(
                "home-assistant-tests-direct-async-setup-entry",
                node=node,
            )
        elif kind == "platform":
            self.add_message(
                "home-assistant-tests-direct-platform-async-setup-entry",
                node=node,
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DirectAsyncSetupEntry(linter))
