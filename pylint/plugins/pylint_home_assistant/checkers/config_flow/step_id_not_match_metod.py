"""Checker for detecting IP-based unique IDs in config entries.

Using an IP address or hostname as a config entry's ``unique_id`` breaks when
the device gets a new DHCP lease. The unique ID must be something stable -- a
MAC address (formatted via ``format_mac``), serial number, or other hardware b
identifier.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module
from pylint_home_assistant.helpers.module_info import parse_module

# Methods that has a `step_id` parameter.
CALLERS = {
    "async_show_form",
    "async_external_step",
    "async_show_progress",
    "async_show_menu",
}


class HassEnforceConfigEntryStepIdMatchMethodChecker(BaseChecker):
    """Checker for IP/hostname-based unique IDs."""

    name = "home_assistant_enforce_config_entry_step_id_match_method"
    priority = -1
    msgs = {
        "W8989": (
            "The step_id '%s' does not match the method name '%s'; "
            "the step_id should match the method name after"
            " removing the 'async_step_' prefix.",
            "home-assistant-step_id-match-method",
            "Used when the step_id does not match the method name. "
            "The step_id should match the method name after removing the "
            "'async_step_' prefix. ",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check calls."""
        parsed = parse_module(node.root().name)
        if parsed is None or parsed.module != Module.CONFIG_FLOW:
            return

        if not isinstance(node.func, nodes.Attribute):
            return
        if node.func.attrname not in CALLERS:
            return

        parent = node.parent.parent
        method: str = parent.name
        method_step_id = method.removeprefix("async_step_")

        step_id_node: nodes.NodeNG | None = None
        if node.keywords:
            for keyword in node.keywords:
                if keyword.arg == "step_id":
                    step_id_node = keyword.value
                    break

        if step_id_node is None:
            return
        step_id_node = step_id_node.value

        if step_id_node != method_step_id:
            self.add_message(
                "home-assistant-step_id-match-method",
                node=node,
                args=(
                    step_id_node,
                    method,
                ),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConfigEntryStepIdMatchMethodChecker(linter))
