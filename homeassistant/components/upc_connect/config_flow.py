"""Config flow for UPC Connect integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_IP = "192.168.0.1"


async def validate_sensor_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    device_trackers: dict[str, list] = handler.options.setdefault(
        DEVICE_TRACKER_DOMAIN, {}
    )
    _LOGGER.info(
        "validate_sensor_setup:: device_trackers=%s, user_input=%s",
        device_trackers,
        user_input,
    )

    return {}


async def validate_import_sensor_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    # device_trackers: dict[str, list] = handler.options.setdefault(
    #     DEVICE_TRACKER_DOMAIN, {}
    # )

    async_create_issue(
        handler.parent_handler.hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.7.0",
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "UPC Connect",
        },
    )
    return {}


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=vol.Schema(
            {
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_HOST, default=DEFAULT_IP): str,
            }
        )
    ),
    "import": SchemaFlowFormStep(
        schema=vol.Schema({}),
        validate_user_input=validate_import_sensor_setup,
    ),
}


class UpcConnectConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Upc Connect."""

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return "UPC Connect"

    @callback
    def async_create_entry(self, data: Mapping[str, Any], **kwargs: Any) -> FlowResult:
        """Finish config flow and create a config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")
        return super().async_create_entry(data, **kwargs)
