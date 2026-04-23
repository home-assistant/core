"""Plugin for detecting polling interval fields in config flow schemas.

Polling intervals (scan_interval, update_interval, etc.) should be fixed
by the integration, not exposed as user-configurable fields. The integration
author determines the appropriate polling frequency based on API rate limits,
device capabilities, and data freshness needs.

Found in 3.5% of new-integration PRs across 1,100+ analyzed PRs, April 2026.
"""

from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

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
    """Checker for polling interval fields in config flow schemas.

    Config flows should not include polling interval fields
    (CONF_SCAN_INTERVAL, "scan_interval", "update_interval", etc.) -- these
    should be fixed by the integration author, not user-configurable.
    """

    name = "hass_enforce_config_flow_no_polling"
    priority = -1
    msgs = {
        "W7492": (
            "Config flow should not include a '%s' field -- polling intervals "
            "should be fixed by the integration, not user-configurable "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/appropriate-polling)",
            "hass-config-flow-polling-field",
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
        root_name = node.root().name
        if not root_name.startswith("homeassistant.components."):
            return

        parts = root_name.split(".")
        current_module = parts[3] if len(parts) > 3 else ""
        if current_module != "config_flow":
            return

        field_name = _get_schema_field_name(node)
        if field_name is None:
            return

        if field_name in _POLLING_FIELD_NAMES:
            self.add_message(
                "hass-config-flow-polling-field",
                node=node,
                args=(field_name,),
            )


def _get_schema_field_name(node: nodes.Call) -> str | None:
    """Extract the field name from vol.Required(...) or vol.Optional(...)."""
    if not isinstance(node.func, nodes.Attribute):
        return None
    if node.func.attrname not in {"Required", "Optional"}:
        return None
    if not node.args:
        return None

    first_arg = node.args[0]
    if isinstance(first_arg, nodes.Const) and isinstance(first_arg.value, str):
        return first_arg.value
    if isinstance(first_arg, nodes.Name):
        return str(first_arg.name)
    return None


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConfigFlowNoPollingChecker(linter))
