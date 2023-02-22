"""Config flow for Anova."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class AnovaConfligFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Sets up a config flow for Anova."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            await self.async_set_unique_id(user_input["device_unique_id"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Anova",
                data={"device_unique_id": user_input["device_unique_id"]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("device_unique_id"): str}),
        )
