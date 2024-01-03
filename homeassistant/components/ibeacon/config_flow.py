"""Config flow for iBeacon Tracker integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class IBeaconConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iBeacon Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not bluetooth.async_scanner_count(self.hass, connectable=False):
            return self.async_abort(reason="bluetooth_not_available")

        if user_input is not None:
            return self.async_create_entry(title="iBeacon Tracker", data={})

        return self.async_show_form(step_id="user")
