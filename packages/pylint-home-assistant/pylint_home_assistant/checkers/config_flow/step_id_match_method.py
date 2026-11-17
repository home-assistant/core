"""Checker for step_id does not match method name.

The step_id parameter for async_show_form, async_external_step,
async_show_progress, and async_show_menu should match the method
name after removing the 'async_step_' prefix. For example,
if the method is named async_step_user, the step_id should be 'user'.
"""

from astroid import InferenceError, nodes
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
        "W7443": (
            (
                "The step_id '%s' does not match the method name '%s'; "
                "the step_id should match the method name after"
                " removing the 'async_step_' prefix."
            ),
            "home-assistant-step_id-match-method",
            (
                "Used when the step_id does not match the method name. "
                "The step_id should match the method name after removing the "
                "'async_step_' prefix. Show a form by moving to that step "
                "first using 'return await self.async_step_<step_id>'."
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

        step_ids: list[str] = []
        for keyword in node.keywords:
            if keyword.arg != "step_id":
                continue
            try:
                inferred_values = list(keyword.value.infer())
            except InferenceError:
                break
            for inferred in inferred_values:
                if (
                    isinstance(inferred, nodes.Const)
                    and isinstance(inferred.value, str)
                    and inferred.value not in step_ids
                ):
                    step_ids.append(inferred.value)
            break

        if not step_ids or method_step_id is None:
            # No string step_id could be inferred or the call is not in a step method
            return

        if step_ids != [method_step_id]:
            self.add_message(
                "home-assistant-step_id-match-method",
                node=node,
                args=(
                    ", ".join(step_ids),
                    f"async_step_{method_step_id}",
                ),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConfigEntryStepIdMatchMethodChecker(linter))
