"""Adds config flow for Time & Date integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.core import async_get_hass
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_DISPLAY_OPTIONS, DOMAIN, OPTION_TYPES

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DISPLAY_OPTIONS): SelectSelector(
            SelectSelectorConfig(
                options=OPTION_TYPES,
                mode=SelectSelectorMode.DROPDOWN,
                multiple=True,
                translation_key="display_options",
            )
        ),
    }
)


async def validate_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate rest setup."""
    hass = async_get_hass()
    if hass.config.time_zone is None:
        raise SchemaFlowError("timezone_not_exist")
    return user_input


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA,
        validate_user_input=validate_input,
    ),
    "import": SchemaFlowFormStep(
        schema=DATA_SCHEMA,
        validate_user_input=validate_input,
    ),
}
OPTIONS_FLOW = {"init": SchemaFlowFormStep(schema=DATA_SCHEMA)}


class TimeDateConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Time & Date."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return "Time & Date"

    def async_config_flow_finished(self, options: Mapping[str, Any]) -> None:
        """Abort if instance already exist."""
        if self._async_current_entries():
            raise data_entry_flow.AbortFlow("single_instance_allowed")
