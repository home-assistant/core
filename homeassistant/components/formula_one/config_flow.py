"""Config flow for Formula 1 integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .coordinator import F1UpdateCoordinator


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Formula 1."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # This integration should not be setup more than once
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors = {}

        if user_input is not None:
            if not await F1UpdateCoordinator(self.hass).test_connect():
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Formula 1", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({}), errors=errors
        )
