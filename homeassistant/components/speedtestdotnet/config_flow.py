"""Config flow for Speedtest.net."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_SERVER_ID,
    CONF_SERVER_NAME,
    DEFAULT_NAME,
    DEFAULT_SERVER,
    DOMAIN,
)


class SpeedTestFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Speedtest.net config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SpeedTestOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SpeedTestOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")

        return self.async_create_entry(title=DEFAULT_NAME, data=user_input)


class SpeedTestOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle SpeedTest options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._servers: dict = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            server_name = user_input[CONF_SERVER_NAME]
            if server_name != "*Auto Detect":
                server_id = self._servers[server_name]["id"]
                user_input[CONF_SERVER_ID] = server_id
            else:
                user_input[CONF_SERVER_ID] = None

            return self.async_create_entry(title="", data=user_input)

        self._servers = self.hass.data[DOMAIN].servers

        options = {
            vol.Optional(
                CONF_SERVER_NAME,
                default=self.config_entry.options.get(CONF_SERVER_NAME, DEFAULT_SERVER),
            ): vol.In(self._servers.keys()),
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options), errors=errors
        )
