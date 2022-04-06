"""Config flow to configure the Uptime integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DOMAIN


class UptimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Uptime."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={},
            )

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(user_input)
