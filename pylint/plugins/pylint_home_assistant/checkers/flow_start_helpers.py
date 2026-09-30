"""Checker for manually started reauth and reconfigure flows in tests.

Tests should start these flows with the ``MockConfigEntry`` helpers
(``start_reauth_flow`` / ``start_reconfigure_flow``) instead of calling
``hass.config_entries.flow.async_init`` with a hand-built context. The helpers
build the same context Home Assistant uses at runtime.

``W7438`` (``home-assistant-test-flow-start-helper``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import parse_module

_SOURCES = {
    "SOURCE_REAUTH": ("reauth", "start_reauth_flow"),
    "SOURCE_RECONFIGURE": ("reconfigure", "start_reconfigure_flow"),
}
_LITERALS = dict(_SOURCES.values())


def _get_helper(node: nodes.NodeNG) -> str | None:
    """Return the helper replacing the given source value, if any."""
    match node:
        case nodes.Name(name=name) | nodes.Attribute(attrname=name):
            if name in _SOURCES:
                return _SOURCES[name][1]
        case nodes.Const(value=str() as value):
            return _LITERALS.get(value)
    return None


def _get_source_helper(call: nodes.Call) -> str | None:
    """Return the helper for a flow init call with a reauth/reconfigure source."""
    context = call.keywords and next(
        (kw.value for kw in call.keywords if kw.arg == "context"), None
    )
    if not isinstance(context, nodes.Dict):
        return None
    for key, value in context.items:
        if isinstance(key, nodes.Const) and key.value == "source":
            return _get_helper(value)
    return None


class FlowStartHelpersChecker(BaseChecker):
    """Checker for manually started reauth/reconfigure flows in tests."""

    name = "home_assistant_flow_start_helpers"
    priority = -1
    msgs = {
        "W7438": (
            "Use `entry.%s(hass)` instead of starting the flow manually "
            "with `async_init`",
            "home-assistant-test-flow-start-helper",
            "Used when a test starts a reauth or reconfigure flow by calling "
            "`async_init` with a manually built context. Use the "
            "`MockConfigEntry` helpers instead.",
        ),
    }
    options = ()

    _in_integration_test: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration test module."""
        self._in_integration_test = parse_module(
            node.name, include_test=True
        ) is not None and node.name.startswith("tests.")

    def visit_call(self, node: nodes.Call) -> None:
        """Check flow init calls."""
        if not self._in_integration_test:
            return
        if not (
            isinstance(node.func, nodes.Attribute)
            and node.func.attrname == "async_init"
        ):
            return
        if (helper := _get_source_helper(node)) is None:
            return
        self.add_message(
            "home-assistant-test-flow-start-helper", node=node, args=(helper,)
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(FlowStartHelpersChecker(linter))
