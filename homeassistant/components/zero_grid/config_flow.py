"""Config flow for Zero Grid integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class ZeroGridConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zero Grid."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title="Zero Grid",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required("name", default="Zero Grid"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
