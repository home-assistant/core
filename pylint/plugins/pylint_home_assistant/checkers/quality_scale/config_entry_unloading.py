"""Checker for missing config entry unloading.

**Quality-scale-gated** (Silver): only fires for integrations whose
``quality_scale.yaml`` marks ``config-entry-unloading`` as ``done``.

The integration's ``__init__.py`` must implement ``async_unload_entry``
so that config entries can be properly unloaded and resources cleaned up.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-entry-unloading/
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module, QualityScaleRule
from pylint_home_assistant.helpers.module_info import get_module_platform
from pylint_home_assistant.helpers.quality_scale import quality_scale_rule_is_done


class ConfigEntryUnloadingChecker(BaseChecker):
    """Checker for async_unload_entry in __init__ modules."""

    name = "home_assistant_config_entry_unloading"
    priority = -1
    msgs = {
        "W7413": (
            "Integration should implement `async_unload_entry` "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/config-entry-unloading)",
            "home-assistant-missing-config-entry-unloading",
            "Used when an integration's __init__.py does not implement "
            "async_unload_entry. This function is needed so config entries "
            "can be properly unloaded and resources cleaned up.",
        ),
    }
    options = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Check that __init__ modules define async_unload_entry."""
        platform = get_module_platform(node.name)
        if platform != Module.INIT:
            return

        if not quality_scale_rule_is_done(
            node, QualityScaleRule.CONFIG_ENTRY_UNLOADING
        ):
            return

        # Check top-level function definitions only (not nested)
        for item in node.body:
            if (
                isinstance(item, nodes.AsyncFunctionDef)
                and item.name == "async_unload_entry"
            ):
                return

        self.add_message("home-assistant-missing-config-entry-unloading", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(ConfigEntryUnloadingChecker(linter))
