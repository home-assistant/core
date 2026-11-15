"""Checker for unnecessary ``format_mac`` in ``CONNECTION_NETWORK_MAC`` tuples.

The device registry normalizes ``CONNECTION_NETWORK_MAC`` connections
through ``format_mac()`` in ``_normalize_connections()`` before storing
them. Calling ``format_mac()`` in integration code when constructing
connection tuples passed to device registry API methods is therefore
redundant.

Only tuples inside a ``connections=`` keyword argument are flagged.
Tuples used for direct comparison against ``device.connections``
(e.g. ``in``, set intersection) legitimately need ``format_mac()``
because those comparisons bypass the device registry normalization.

``W7429`` (``home-assistant-unnecessary-format-mac``)
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module


def _is_connection_network_mac(node: nodes.NodeNG) -> bool:
    """Check if a node refers to CONNECTION_NETWORK_MAC."""
    match node:
        case nodes.Name(name="CONNECTION_NETWORK_MAC"):
            return True
        case nodes.Attribute(attrname="CONNECTION_NETWORK_MAC"):
            return True
    return False


def _is_format_mac_call(node: nodes.NodeNG) -> bool:
    """Check if a node is a call to format_mac()."""
    if not isinstance(node, nodes.Call):
        return False
    match node.func:
        case nodes.Name(name="format_mac"):
            return True
        case nodes.Attribute(attrname="format_mac"):
            return True
    return False


def _is_inside_connections_kwarg(node: nodes.NodeNG) -> bool:
    """Check if a node is inside a ``connections=`` keyword argument."""
    current = node.parent
    while current is not None:
        match current:
            case nodes.Keyword(arg="connections"):
                return True
            case nodes.FunctionDef() | nodes.ClassDef() | nodes.Module():
                break
        current = current.parent
    return False


class UnnecessaryFormatMacChecker(BaseChecker):
    """Checker for unnecessary format_mac in CONNECTION_NETWORK_MAC tuples."""

    name = "home_assistant_unnecessary_format_mac"
    priority = -1
    msgs = {
        "W7429": (
            "format_mac() is unnecessary with CONNECTION_NETWORK_MAC; "
            "the device registry normalizes MAC addresses automatically",
            "home-assistant-unnecessary-format-mac",
            "Used when format_mac() is called inside a connection tuple "
            "with CONNECTION_NETWORK_MAC that is passed to a device "
            "registry API method via connections=. The device registry "
            "already normalizes MAC addresses via "
            "_normalize_connections(), so the call is redundant.",
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_tuple(self, node: nodes.Tuple) -> None:
        """Check connection tuples for unnecessary format_mac calls."""
        if not self._in_integration:
            return

        if len(node.elts) != 2:
            return

        key, value = node.elts

        if not _is_connection_network_mac(key):
            return

        if not _is_format_mac_call(value):
            return

        if not _is_inside_connections_kwarg(node):
            return

        self.add_message(
            "home-assistant-unnecessary-format-mac",
            node=value,
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(UnnecessaryFormatMacChecker(linter))
