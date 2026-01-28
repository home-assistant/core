"""Config flow for Lytiva integration."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class LytivaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lytiva."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if "mqtt" not in self.hass.config_entries.async_domains():
            return self.async_abort(reason="mqtt_not_connected")

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Lytiva", data={})

        return self.async_show_form(step_id="user")
