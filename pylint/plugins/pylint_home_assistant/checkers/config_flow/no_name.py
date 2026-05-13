"""Checker for detecting name fields in config flow schemas.

Config flows should not ask users to provide a name for the device or
integration entry. The name is automatically derived from the device (via
discovery) or set by the integration code itself.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module
from pylint_home_assistant.helpers.ast_utils import (
    get_schema_field_name,
    is_in_subentry_flow,
)
from pylint_home_assistant.helpers.integration import is_helper_integration
from pylint_home_assistant.helpers.module_info import parse_module

# Field names that indicate a "name" field in a config flow schema.
_NAME_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "CONF_DEVICE_NAME",
        "CONF_NAME",
        "device_name",
        "name",
    }
)


class HassEnforceConfigFlowNoNameChecker(BaseChecker):
    """Checker for name fields in config flow schemas."""

    name = "home_assistant_enforce_config_flow_no_name"
    priority = -1
    msgs = {
        "W7408": (
            "Config flow should not include a '%s' field -- names are derived "
            "from discovery or set by the integration code",
            "home-assistant-config-flow-name-field",
            "Used when a config flow schema includes a name field. Users "
            "should not set names in config flows; they come automatically "
            "from the device (via discovery) or are set by the integration.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check for name fields in vol.Required/Optional calls."""
        parsed = parse_module(node.root().name)
        if parsed is None or parsed.module != Module.CONFIG_FLOW:
            return

        # Check field name first (cheap) before doing heavier checks.
        field_name = get_schema_field_name(node)
        if field_name is None or field_name not in _NAME_FIELD_NAMES:
            return

        # Helper integrations legitimately ask users for a name since there
        # is no device to discover the name from.
        if is_helper_integration(parsed.domain, node.root()):
            return

        # Subentry flows may legitimately ask for a name.
        if is_in_subentry_flow(node):
            return

        self.add_message(
            "home-assistant-config-flow-name-field",
            node=node,
            args=(field_name,),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConfigFlowNoNameChecker(linter))
