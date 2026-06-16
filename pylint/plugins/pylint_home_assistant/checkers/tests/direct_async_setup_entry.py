"""Checker for direct calls to ``async_setup_entry`` from tests.

Tests should not invoke an integration's ``async_setup_entry`` directly
(either the one in ``__init__.py`` or in an entity-platform module).
Instead, tests should let Home Assistant perform the setup via
``await hass.config_entries.async_setup(entry.entry_id)`` so that the
real setup pipeline (platforms, services, listeners, unload handlers,
etc.) is exercised.

This checker flags any call to ``async_setup_entry`` (whether awaited or
not, accessed as a name or an attribute) made from a test module whose
target resolves to a module-level function defined under
``homeassistant.components.*``. The integration-init case and the
entity-platform case get separate messages so violations can be tracked
and fixed independently.
"""

from enum import Enum

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module, parse_module


class _SetupKind(Enum):
    """The kind of integration ``async_setup_entry`` being called."""

    INIT = "init"
    PLATFORM = "platform"


def _resolve_integration_async_setup_entry(call: nodes.Call) -> _SetupKind | None:
    """Return the kind of integration ``async_setup_entry`` *call* targets.

    Returns ``_SetupKind.INIT`` if the target is in the integration's
    ``__init__`` module, ``_SetupKind.PLATFORM`` if it is in an
    entity-platform module, or ``None`` if the call does not resolve to
    an integration's ``async_setup_entry``.
    """
    func = call.func
    match func:
        case nodes.Attribute(attrname="async_setup_entry"):
            pass
        case nodes.Name(name="async_setup_entry"):
            pass
        case _:
            return None

    seen_qnames: set[str] = set()
    try:
        for inferred in func.infer():
            if inferred is astroid.Uninferable:
                continue
            if not isinstance(inferred, (nodes.FunctionDef, nodes.AsyncFunctionDef)):
                continue
            # Require the function to be defined at module level so that
            # class methods named ``async_setup_entry`` (whose qname
            # includes the class name) are not classified as integration
            # setup functions.
            if not isinstance(inferred.parent, nodes.Module):
                continue
            module_qname = inferred.parent.qname()
            if not module_qname or module_qname in seen_qnames:
                continue
            seen_qnames.add(module_qname)
            parsed = parse_module(module_qname)
            if parsed is None:
                continue
            return _SetupKind.INIT if parsed.module is None else _SetupKind.PLATFORM
    except astroid.exceptions.InferenceError, astroid.exceptions.AstroidError:
        return None
    return None


class DirectAsyncSetupEntry(BaseChecker):
    """Checker for direct calls to async_setup_entry in tests."""

    name = "home_assistant_tests_direct_async_setup_entry"
    priority = -1
    msgs = {
        "W7418": (
            (
                "Do not call `async_setup_entry` directly from tests; use "
                "`await hass.config_entries.async_setup(entry.entry_id)` instead"
            ),
            "home-assistant-tests-direct-async-setup-entry",
            (
                "Used when a test module calls an integration's "
                "`async_setup_entry` from `__init__.py` directly. Tests should "
                "let Home Assistant drive the setup so the full setup pipeline "
                "is exercised."
            ),
        ),
        "W7420": (
            (
                "Do not call a platform's `async_setup_entry` directly from "
                "tests; use `await hass.config_entries.async_setup(entry.entry_id)`"
                " instead"
            ),
            "home-assistant-tests-direct-platform-async-setup-entry",
            (
                "Used when a test module calls an integration entity platform's "
                "`async_setup_entry` directly. Tests should let Home Assistant "
                "drive the setup so the full setup pipeline is exercised."
            ),
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
        match _resolve_integration_async_setup_entry(node):
            case _SetupKind.INIT:
                self.add_message(
                    "home-assistant-tests-direct-async-setup-entry",
                    node=node,
                )
            case _SetupKind.PLATFORM:
                self.add_message(
                    "home-assistant-tests-direct-platform-async-setup-entry",
                    node=node,
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DirectAsyncSetupEntry(linter))
