"""Config flow for Swing2Sleep Smarla integration."""

from __future__ import annotations

from typing import Any

from pysmarlaapi import Connection
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, HOST, HOST_DEV


class SmarlaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Swing2Sleep Smarla."""

    VERSION = 1

    async def _handle_token(
        self, token: str, host: str = HOST
    ) -> tuple[dict[str, str], str | None]:
        """Handle the token input."""
        errors: dict[str, str] = {}

        try:
            conn = Connection(url=host, token_b64=token)
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
            host = user_input.get(CONF_HOST, HOST)
            raw_token = user_input[CONF_ACCESS_TOKEN]
            errors, serial_number = await self._handle_token(token=raw_token, host=host)

            if not errors and serial_number is not None:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=serial_number,
                    data={CONF_ACCESS_TOKEN: raw_token, CONF_HOST: host},
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): str,
            }
        )

        if self.show_advanced_options:
            data_schema = data_schema.extend(
                {
                    vol.Optional(CONF_HOST): SelectSelector(
                        SelectSelectorConfig(
                            options=[HOST, HOST_DEV],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
