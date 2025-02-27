"""Config flow for Tilt Pi integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=1880): int,
    }
)


class TiltPiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tilt Pi."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a configuration flow initialized by the user."""

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=USER_DATA_SCHEMA,
            )

        # Check if device is already configured
        await self.async_set_unique_id(f"tiltpi_{user_input[CONF_HOST]}")
        self._abort_if_unique_id_configured()

        errors = {}

        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                f"http://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}/macid/all",
                timeout=aiohttp.ClientTimeout(10),
            ) as resp:
                resp.raise_for_status()
                await resp.json()

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )
        except (TimeoutError, aiohttp.ClientError):
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="user",
                data_schema=USER_DATA_SCHEMA,
                errors=errors,
            )
