"""Options flow for Solvis Remote integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_OPTION_OVEN,
    CONF_OPTION_SOLAR,
    CONF_OPTION_SOLAR_EAST_WEST,
    CONF_OPTION_TITEL,
    CONF_OPTION_WARMWATER_STATION,
    CONF_UPDATE_TIMESPAN,
)

_LOGGER = logging.getLogger(__name__)


STEP_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTION_WARMWATER_STATION, default=True): bool,
        vol.Required(CONF_OPTION_SOLAR, default=True): bool,
        vol.Required(CONF_OPTION_SOLAR_EAST_WEST, default=False): bool,
        vol.Required(CONF_OPTION_OVEN, default=False): bool,
        vol.Required(CONF_UPDATE_TIMESPAN, default=10): int,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Set up Options Flow Handler."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options for the custom component."""
        errors: dict[str, str] = {}

        # Grab all configured repos from the entity registry so we can populate the
        # multi-select dropdown that will allow a user to remove a repo.
        entity_reg = er.async_get(self.hass)
        er.async_entries_for_config_entry(entity_reg, self.config_entry.entry_id)

        if user_input is not None:
            # Validation and additional processing logic omitted for brevity.
            # ...
            if not errors:
                # Value of data will be set on the options property of our config_entry
                # instance.
                return self.async_create_entry(title=CONF_OPTION_TITEL, data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=STEP_OPTIONS_SCHEMA, errors=errors
        )
