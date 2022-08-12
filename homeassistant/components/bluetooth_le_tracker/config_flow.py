"""Config flow for Bluetooth LE Tracker integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_TRACK_BATTERY,
    CONF_TRACK_BATTERY_INTERVAL,
    DEFAULT_TRACK_BATTERY,
    DEFAULT_TRACK_BATTERY_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _async_build_schema_with_user_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> vol.Schema:
    track_battery = user_input.get(CONF_TRACK_BATTERY, DEFAULT_TRACK_BATTERY)
    track_battery_interval = user_input.get(
        CONF_TRACK_BATTERY_INTERVAL, DEFAULT_TRACK_BATTERY_INTERVAL
    )
    schema = {
        vol.Required(CONF_TRACK_BATTERY, default=track_battery): str,
        vol.Required(CONF_TRACK_BATTERY_INTERVAL, default=track_battery_interval): int,
    }
    return vol.Schema(schema)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bluetooth LE Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Bluetooth LE Tracker", data={})

        return self.async_show_form(step_id="user")

    async def async_step_import(self, options: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(
            title="Bluetooth LE Tracker", data={}, options=options
        )
