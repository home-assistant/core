"""Config flow for Airzone."""
from __future__ import annotations

from typing import Any

from aioairzone.const import DEFAULT_PORT, DEFAULT_SYSTEM_ID
from aioairzone.exceptions import AirzoneError, InvalidSystem
from aioairzone.localapi import AirzoneLocalApi, ConnectionOptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)
SYSTEM_ID_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_ID, default=1): int,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for an Airzone device."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        data_schema = CONFIG_SCHEMA
        errors = {}

        if user_input is not None:
            system_id = user_input.get(CONF_ID, DEFAULT_SYSTEM_ID)

            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_ID: system_id,
                }
            )

            airzone = AirzoneLocalApi(
                aiohttp_client.async_get_clientsession(self.hass),
                ConnectionOptions(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    system_id,
                ),
            )

            try:
                await airzone.validate()
            except InvalidSystem:
                data_schema = SYSTEM_ID_SCHEMA
                errors["base"] = "invalid_system_id"
            except AirzoneError:
                errors["base"] = "cannot_connect"
            else:
                title = f"Airzone {user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
