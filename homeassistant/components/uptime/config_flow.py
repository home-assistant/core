"""Config flow to configure the Uptime integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class UptimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Uptime."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(
                title="Uptime",
                data={},
            )

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
