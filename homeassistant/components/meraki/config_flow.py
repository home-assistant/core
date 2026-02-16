"""Config flow for Meraki."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SECRET, CONF_VALIDATOR, DOMAIN


class MerakiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meraki."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Meraki", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_VALIDATOR): str,
                vol.Required(CONF_SECRET): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)
