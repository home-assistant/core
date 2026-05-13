"""Plugin for verifying reconfigure flow quality scale claims.

When an integration marks ``reconfigure-flow: done`` in its
``quality_scale.yaml``, its ``config_flow.py`` must define an
``async_step_reconfigure`` method on the config flow class.

This checker is **quality-scale-gated**: it only fires for integrations
whose ``quality_scale.yaml`` marks ``reconfigure-flow`` as ``done``.
"""

from _hass_quality_scale_helpers import get_integration_dir, quality_scale_rule_is_done
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassEnforceReconfigureFlowChecker(BaseChecker):
    """Checker for missing reconfigure flow.

    Only fires for integrations whose ``quality_scale.yaml`` marks
    ``reconfigure-flow`` as ``done``.
    """

    name = "hass_enforce_reconfigure_flow"
    priority = -1
    msgs = {
        "W7483": (
            "Integration claims reconfigure-flow: done but config_flow.py "
            "has no async_step_reconfigure method "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/reconfigure-flow)",
            "hass-reconfigure-flow-missing",
            "Used when quality_scale.yaml marks reconfigure-flow as done "
            "but the config flow class does not implement "
            "async_step_reconfigure. "
            "See https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/reconfigure-flow",
        ),
    }
    options = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Check config_flow.py for async_step_reconfigure."""
        root_name = node.name
        if not root_name.startswith("homeassistant.components."):
            return

        parts = root_name.split(".")
        current_module = parts[3] if len(parts) > 3 else ""
        if current_module != "config_flow":
            return

        integration_dir = get_integration_dir(node)
        if not integration_dir:
            return

        if not quality_scale_rule_is_done(integration_dir, "reconfigure-flow"):
            return

        if _has_step_method(node, "async_step_reconfigure"):
            return

        self.add_message("hass-reconfigure-flow-missing", node=node)


def _has_step_method(module: nodes.Module, method_name: str) -> bool:
    """Return True if any class in the module defines the given method."""
    for child in module.body:
        if not isinstance(child, nodes.ClassDef):
            continue
        for item in child.body:
            if isinstance(item, nodes.FunctionDef) and item.name == method_name:
                return True
    return False


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceReconfigureFlowChecker(linter))
