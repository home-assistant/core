"""Config flow for ClimaCell integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_TIMESTEP, DEFAULT_TIMESTEP, DOMAIN


class ClimaCellOptionsConfigFlow(config_entries.OptionsFlow):
    """Handle ClimaCell options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize ClimaCell options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the ClimaCell options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = {
            vol.Required(
                CONF_TIMESTEP,
                default=self._config_entry.options.get(CONF_TIMESTEP, DEFAULT_TIMESTEP),
            ): vol.In([1, 5, 15, 30]),
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options_schema)
        )


class ClimaCellConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ClimaCell Weather API."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ClimaCellOptionsConfigFlow:
        """Get the options flow for this handler."""
        return ClimaCellOptionsConfigFlow(config_entry)
