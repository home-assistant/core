"""Checker for missing reauthentication flow in config flow.

**Quality-scale-gated** (Silver): only fires for integrations whose
``quality_scale.yaml`` marks ``reauthentication-flow`` as ``done``.

The config flow must implement ``async_step_reauth`` so that users can
re-authenticate when credentials expire or become invalid.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow/
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module, QualityScaleRule
from pylint_home_assistant.helpers.module_info import get_module_platform
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_done


class ReauthenticationFlowChecker(BaseChecker):
    """Checker for async_step_reauth in config flow modules."""

    name = "home_assistant_reauthentication_flow"
    priority = -1
    msgs = {
        "W7410": (
            "Integration config flow should implement `async_step_reauth` "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/reauthentication-flow)",
            "home-assistant-missing-reauthentication-flow",
            "Used when an integration's config_flow.py does not implement "
            "async_step_reauth. This method is needed so users can "
            "re-authenticate when credentials expire.",
        ),
    }
    options = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Check that config_flow modules define async_step_reauth."""
        platform = get_module_platform(node.name)
        if platform != Module.CONFIG_FLOW:
            return

        if not quality_scale_rule_is_done(node, QualityScaleRule.REAUTHENTICATION_FLOW):
            return

        for child in node.nodes_of_class(nodes.AsyncFunctionDef):
            if child.name == "async_step_reauth":
                return

        self.add_message("home-assistant-missing-reauthentication-flow", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ReauthenticationFlowChecker(linter))
