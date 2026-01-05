"""Config flow for Swing2Sleep Smarla integration."""

from __future__ import annotations

from typing import Any

from pysmarlaapi import Connection
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import DOMAIN, HOST

STEP_USER_DATA_SCHEMA = vol.Schema({CONF_ACCESS_TOKEN: str})


class SmarlaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Swing2Sleep Smarla."""

    VERSION = 1

    async def _handle_token(self, token: str) -> tuple[dict[str, str], str | None]:
        """Handle the token input."""
        errors: dict[str, str] = {}

        try:
            conn = Connection(url=HOST, token_b64=token)
        except ValueError:
            errors["base"] = "malformed_token"
            return errors, None

        if not await conn.refresh_token():
            errors["base"] = "invalid_auth"
            return errors, None

        return errors, conn.token.serialNumber

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            raw_token = user_input[CONF_ACCESS_TOKEN]
            errors, serial_number = await self._handle_token(token=raw_token)

            if not errors and serial_number is not None:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=serial_number,
                    data={CONF_ACCESS_TOKEN: raw_token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
