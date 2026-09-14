"""Checker for step_id does not match method name.

The step_id parameter for async_show_form, async_external_step,
async_show_progress, and async_show_menu should match the method
name after removing the 'async_step_' prefix. For example,
if the method is named async_step_user, the step_id should be 'user'.
"""

from astroid import InferenceError, Uninferable, nodes
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
    """Checker for config-flow step id that do not match their method name."""

    name = "home_assistant_enforce_config_entry_step_id_match_method"
    priority = -1
    msgs = {
        "W7438": (
            (
                "The step_id '%s' does not match the method name '%s'; "
                "the step_id should match the method name after"
                " removing the 'async_step_' prefix."
            ),
            "home-assistant-step_id-match-method",
            (
                "Used when the step_id does not match the method name. "
                "The step_id should match the method name after removing the "
                "'async_step_' prefix. "
            ),
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

        method_step_id: str | None = None
        for ancestor in node.func.node_ancestors():
            if isinstance(
                ancestor, nodes.AsyncFunctionDef
            ) and ancestor.name.startswith("async_step_"):
                method_step_id = ancestor.name.removeprefix("async_step_")
                break

        step_id_node: nodes.NodeNG | None = None
        if node.keywords:
            for keyword in node.keywords:
                if keyword.arg == "step_id":
                    try:
                        values = list(keyword.value.infer())
                    except InferenceError:
                        values = []
                    if values[0] is Uninferable:
                        values = []
                    if len(values) > 1:
                        step_id_node = "__INCORRECT__"
                        break
                    step_id_node = values[0].value if values else None
                    break

        if step_id_node is None or method_step_id is None:
            # step_id is None when it follows the method directly
            return

        if step_id_node != method_step_id:
            self.add_message(
                "home-assistant-step_id-match-method",
                node=node,
                args=(
                    step_id_node,
                    f"async_step_{method_step_id}",
                ),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConfigEntryStepIdMatchMethodChecker(linter))
