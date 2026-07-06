"""Checker for detecting IP-based unique IDs in config entries.

Using an IP address or hostname as a config entry's ``unique_id`` breaks when
the device gets a new DHCP lease. The unique ID must be something stable -- a
MAC address (formatted via ``format_mac``), serial number, or other hardware
identifier.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module
from pylint_home_assistant.helpers.module_info import parse_module

# Config keys that represent host/IP -- used as unique ID sources.
_IP_HOST_NAMES: frozenset[str] = frozenset(
    {
        "CONF_HOST",
        "CONF_IP_ADDRESS",
        "CONF_URL",
        "host",
        "hostname",
        "ip",
        "ip_address",
    }
)


class HassEnforceConfigEntryUniqueIdNoIpChecker(BaseChecker):
    """Checker for IP/hostname-based unique IDs."""

    name = "home_assistant_enforce_config_entry_unique_id_no_ip"
    priority = -1
    msgs = {
        "W7406": (
            "unique_id should not be based on '%s' -- IP addresses change; "
            "use a MAC address (format_mac), serial number, or hardware ID "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/unique-config-entry)",
            "home-assistant-unique-id-ip-based",
            "Used when a unique_id is set from a host/IP config key. IP "
            "addresses change when devices get new DHCP leases. Use a "
            "stable hardware identifier instead. "
            "See https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/unique-config-entry",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check async_set_unique_id(host-based-value) calls."""
        parsed = parse_module(node.root().name)
        if parsed is None or parsed.module != Module.CONFIG_FLOW:
            return

        if not isinstance(node.func, nodes.Attribute):
            return
        if node.func.attrname != "async_set_unique_id":
            return

        unique_id_node: nodes.NodeNG | None = None
        if node.args:
            unique_id_node = node.args[0]
        elif node.keywords:
            for keyword in node.keywords:
                if keyword.arg == "unique_id":
                    unique_id_node = keyword.value
                    break

        if unique_id_node is None:
            return

        # Check the argument directly first
        ref = _value_references_ip(unique_id_node)

        # If the argument is a plain variable, resolve it by scanning
        # assignments in the enclosing function
        if ref is None and isinstance(unique_id_node, nodes.Name):
            ref = _resolve_variable_ip_ref(unique_id_node)

        if ref:
            self.add_message(
                "home-assistant-unique-id-ip-based",
                node=node,
                args=(ref,),
            )


def _value_references_ip(node: nodes.NodeNG) -> str | None:
    """Return the IP/host reference name if the expression looks IP-based."""
    # Direct name: CONF_HOST (only at top level, not recursively,
    # to avoid matching local variables like `host` in `host.api.mac`)
    if isinstance(node, nodes.Name) and node.name in _IP_HOST_NAMES:
        return str(node.name)

    return _check_subscript_or_call_ip(node)


def _check_subscript_or_call_ip(node: nodes.NodeNG) -> str | None:
    """Check for IP references in subscript/call patterns, recursively."""
    match node:
        # Subscript: data[CONF_HOST] or data["host"]
        case nodes.Subscript(
            slice=nodes.Name(name=val) | nodes.Const(value=str(val))
        ) if val in _IP_HOST_NAMES:
            return str(val)
        # Call: data.get(CONF_HOST) or data.get("host")
        case nodes.Call(
            func=nodes.Attribute(attrname="get"),
            args=[nodes.Name(name=val) | nodes.Const(value=str(val)), *_],
        ) if val in _IP_HOST_NAMES:
            return str(val)

    # Recurse into child nodes to catch embedded references (e.g. f-strings),
    # but skip function call arguments -- a call like get_unique_id(host)
    # transforms the value, so the result isn't IP-based.
    if not isinstance(node, nodes.Call):
        for child in node.get_children():
            ref = _check_subscript_or_call_ip(child)
            if ref:
                return ref

    return None


def _resolve_variable_ip_ref(name_node: nodes.Name) -> str | None:
    """Resolve a variable back to its assignments in the enclosing function."""
    # Find the enclosing function
    current = name_node.parent
    while current is not None:
        if isinstance(current, nodes.FunctionDef):
            break
        current = current.parent
    else:
        return None

    # Scan all assignments in the function for this variable name
    for assign in current.nodes_of_class(nodes.Assign):
        for target in assign.targets:
            if (
                isinstance(target, nodes.AssignName)
                and target.name == name_node.name
                and assign.value
            ):
                ref = _check_subscript_or_call_ip(assign.value)
                if ref:
                    return ref

    return None


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConfigEntryUniqueIdNoIpChecker(linter))
