"""Config flow for pvpc_hourly_pricing."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from . import CONF_NAME, UI_CONFIG_SCHEMA, VALID_POWER
from .const import ATTR_POWER, ATTR_POWER_P3, ATTR_TARIFF, DOMAIN


class TariffSelectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for `pvpc_hourly_pricing`."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PVPCOptionsFlowHandler:
        """Get the options flow for this handler."""
        return PVPCOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[ATTR_TARIFF])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=UI_CONFIG_SCHEMA)


class PVPCOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle PVPC options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Fill options with entry data
        power = self.config_entry.options.get(
            ATTR_POWER, self.config_entry.data[ATTR_POWER]
        )
        power_valley = self.config_entry.options.get(
            ATTR_POWER_P3, self.config_entry.data[ATTR_POWER_P3]
        )
        schema = vol.Schema(
            {
                vol.Required(ATTR_POWER, default=power): VALID_POWER,
                vol.Required(ATTR_POWER_P3, default=power_valley): VALID_POWER,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
