"""Config flow for iBeacon Tracker integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import CONF_MIN_RSSI, DEFAULT_MIN_RSSI, DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iBeacon Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not bluetooth.async_scanner_count(self.hass, connectable=False):
            return self.async_abort(reason="bluetooth_not_available")

        if user_input is not None:
            return self.async_create_entry(title="iBeacon Tracker", data={})

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for iBeacons."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MIN_RSSI,
                    default=self.entry.options.get(CONF_MIN_RSSI) or DEFAULT_MIN_RSSI,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=-120, max=-30, step=1, mode=NumberSelectorMode.SLIDER
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
