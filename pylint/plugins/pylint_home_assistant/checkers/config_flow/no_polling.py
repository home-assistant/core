"""Checker for detecting polling interval fields in config flow schemas.

Polling intervals should be fixed by the integration, not exposed as
user-configurable fields in the config flow.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module
from pylint_home_assistant.helpers.ast_utils import get_schema_field_name
from pylint_home_assistant.helpers.module_info import parse_module

# Field names that indicate a polling/scan interval.
_POLLING_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "CONF_POLLING_INTERVAL",
        "CONF_REFRESH_INTERVAL",
        "CONF_SCAN_INTERVAL",
        "CONF_UPDATE_FREQUENCY",
        "CONF_UPDATE_INTERVAL",
        "polling_interval",
        "refresh_interval",
        "scan_interval",
        "update_frequency",
        "update_interval",
    }
)


class HassEnforceConfigFlowNoPollingChecker(BaseChecker):
    """Checker for polling interval fields in config flow schemas."""

    name = "home_assistant_enforce_config_flow_no_polling"
    priority = -1
    msgs = {
        "W7407": (
            "Config flow should not include a '%s' field -- polling intervals "
            "should be fixed by the integration, not user-configurable "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/appropriate-polling)",
            "home-assistant-config-flow-polling-field",
            "Used when a config flow schema includes a polling/scan interval "
            "field. The integration author should determine the appropriate "
            "polling frequency based on API rate limits and data freshness "
            "needs. Polling intervals should not be user-configurable. "
            "See https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/appropriate-polling",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check for polling interval fields in vol.Required/Optional calls."""
        parsed = parse_module(node.root().name)
        if parsed is None or parsed.module != Module.CONFIG_FLOW:
            return

        field_name = get_schema_field_name(node)
        if field_name is None:
            return

        if field_name in _POLLING_FIELD_NAMES:
            self.add_message(
                "home-assistant-config-flow-polling-field",
                node=node,
                args=(field_name,),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConfigFlowNoPollingChecker(linter))
