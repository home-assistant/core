"""Checker for missing diagnostics functions.

**Quality-scale-gated** (Gold): only fires for integrations whose
``quality_scale.yaml`` marks ``diagnostics`` as ``done``.

The integration must have a ``diagnostics.py`` module that implements at
least one of ``async_get_config_entry_diagnostics`` or
``async_get_device_diagnostics``.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/diagnostics/
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module, QualityScaleRule
from pylint_home_assistant.helpers.module_info import get_module_platform
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_done

_DIAGNOSTICS_FUNCTIONS: frozenset[str] = frozenset(
    {
        "async_get_config_entry_diagnostics",
        "async_get_device_diagnostics",
    }
)


class DiagnosticsChecker(BaseChecker):
    """Checker for diagnostics functions in diagnostics modules."""

    name = "home_assistant_diagnostics"
    priority = -1
    msgs = {
        "W7412": (
            "Integration diagnostics module should implement "
            "`async_get_config_entry_diagnostics` or "
            "`async_get_device_diagnostics` "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/diagnostics)",
            "home-assistant-missing-diagnostics",
            "Used when an integration's diagnostics.py does not implement "
            "at least one of async_get_config_entry_diagnostics or "
            "async_get_device_diagnostics.",
        ),
    }
    options = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Check that diagnostics modules define a diagnostics function."""
        platform = get_module_platform(node.name)
        if platform != Module.DIAGNOSTICS:
            return

        if not quality_scale_rule_is_done(node, QualityScaleRule.DIAGNOSTICS):
            return

        for child in node.nodes_of_class(nodes.AsyncFunctionDef):
            if child.name in _DIAGNOSTICS_FUNCTIONS:
                return

        self.add_message("home-assistant-missing-diagnostics", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DiagnosticsChecker(linter))
