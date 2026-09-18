"""Checker for direct calls to ``async_setup`` from tests.

Tests should not invoke an integration's ``async_setup`` directly.
Instead, tests should let Home Assistant perform the setup via the
normal pipeline:

* For integrations with config entries, add a ``MockConfigEntry`` and
  call ``await hass.config_entries.async_setup(entry.entry_id)``.
* For integrations without config entries (system integrations), use
  ``await async_setup_component(hass, DOMAIN, {...})`` from
  ``homeassistant.setup``.

This checker flags any ``await <something>.async_setup(...)`` or
``await async_setup(...)`` call in a test module whose target resolves
to a function defined in an integration's ``__init__`` module under
``homeassistant.components.*``.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module, parse_module


def _is_integration_async_setup(call: nodes.Call) -> bool:
    """Return True if *call* targets an integration's ``async_setup``."""
    func = call.func
    if isinstance(func, nodes.Attribute):
        if func.attrname != "async_setup":
            return False
    elif isinstance(func, nodes.Name):
        if func.name != "async_setup":
            return False
    else:
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
        # ``homeassistant.components.sun.async_setup``. Strip the function
        # name to get the module and parse it.
        module_qname = qname.rsplit(".", 1)[0]
        parsed = parse_module(module_qname)
        if parsed is None:
            continue
        # ``async_setup`` lives in the integration's ``__init__``.
        if parsed.module is None:
            return True
    return False


class DirectAsyncSetup(BaseChecker):
    """Checker for direct calls to async_setup in tests."""

    name = "home_assistant_tests_direct_async_setup"
    priority = -1
    msgs = {
        "W7422": (
            "Do not call `async_setup` directly from tests; set up a "
            "`MockConfigEntry` via `hass.config_entries.async_setup` or use "
            "`async_setup_component` instead",
            "home-assistant-tests-direct-async-setup",
            "Used when a test module calls an integration's `async_setup` "
            "directly. Tests should let Home Assistant drive the setup so "
            "the full setup pipeline is exercised.",
        ),
    }
    options = ()

    _in_test_module: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Record whether the current module is a test module."""
        self._in_test_module = is_test_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Flag direct calls to an integration's async_setup."""
        if not self._in_test_module:
            return
        if _is_integration_async_setup(node):
            self.add_message(
                "home-assistant-tests-direct-async-setup",
                node=node,
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DirectAsyncSetup(linter))
