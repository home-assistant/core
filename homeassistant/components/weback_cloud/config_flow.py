"""Config flow for Weback Cloud Integration integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (  # pylint: disable=relative-beyond-top-level
    CONF_PASSWORD,
    CONF_PHONE_NUMBER,
    CONF_REGION,
    DOMAIN,
)
from .hub import WebackCloudHub  # pylint: disable=relative-beyond-top-level

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION): str,
        vol.Required(CONF_PHONE_NUMBER): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Weback Cloud Integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(user_input[CONF_PHONE_NUMBER])
        self._abort_if_unique_id_configured()

        hub = WebackCloudHub(self.hass, user_input)

        try:
            await hub.authenticate()
        except (Exception,):  # pylint: disable=broad-except
            errors["base"] = "invalid_auth"
        else:
            return self.async_create_entry(
                title=f"User: {user_input[CONF_REGION]}-{user_input[CONF_PHONE_NUMBER]}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
