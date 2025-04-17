"""Config flow for Swing2Sleep Smarla integration."""

from __future__ import annotations

from typing import Any

from pysmarlaapi import Connection
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import DOMAIN, HOST

STEP_USER_DATA_SCHEMA = vol.Schema({CONF_ACCESS_TOKEN: str})


class SmarlaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Swing2Sleep Smarla."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}

        try:
            info = await self.validate_input(user_input)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except InvalidToken:
            errors["base"] = "invalid_token"

        if not errors:
            return self.async_create_entry(
                title=info["title"],
                data={CONF_ACCESS_TOKEN: info.get(CONF_ACCESS_TOKEN)},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def validate_input(self, data: dict[str, Any]):
        """Validate the user input allows us to connect.

        Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
        """
        try:
            conn = Connection(url=HOST, token_b64=data[CONF_ACCESS_TOKEN])
        except ValueError as e:
            raise InvalidToken from e

        await self.async_set_unique_id(conn.token.serialNumber)
        self._abort_if_unique_id_configured()

        if not await conn.get_token():
            raise InvalidAuth

        return {
            "title": conn.token.serialNumber,
            CONF_ACCESS_TOKEN: conn.token.get_string(),
        }


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidToken(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid token."""
