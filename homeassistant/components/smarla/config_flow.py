"""Config flow for Swing2Sleep Smarla integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pysmarlaapi import Connection
from pysmarlaapi.connection.exceptions import (
    AuthenticationException,
    ConnectionException,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import DOMAIN, HOST

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})


class SmarlaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Swing2Sleep Smarla."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.errors: dict[str, str] = {}

    async def _handle_token(self, token: str) -> str | None:
        """Handle the token input."""
        try:
            conn = Connection(url=HOST, token_b64=token)
        except ValueError:
            self.errors["base"] = "malformed_token"
            return None

        try:
            await conn.refresh_token()
        except ConnectionException:
            self.errors["base"] = "cannot_connect"
            return None
        except AuthenticationException:
            self.errors["base"] = "invalid_auth"
            return None

        return conn.token.serialNumber

    async def _validate_input(
        self, user_input: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Validate the user input."""
        token = user_input[CONF_ACCESS_TOKEN]
        serial_number = await self._handle_token(token=token)

        if serial_number is not None:
            await self.async_set_unique_id(serial_number)

            if self.source == SOURCE_REAUTH:
                self._abort_if_unique_id_mismatch()
            else:
                self._abort_if_unique_id_configured()

            return {"token": token, "serial_number": serial_number}

        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        self.errors = {}
        if user_input is not None:
            validated_info = await self._validate_input(user_input)
            if validated_info is not None:
                return self.async_create_entry(
                    title=validated_info["serial_number"],
                    data={CONF_ACCESS_TOKEN: validated_info["token"]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=self.errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        self.errors = {}
        if user_input is not None:
            validated_info = await self._validate_input(user_input)
            if validated_info is not None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_ACCESS_TOKEN: validated_info["token"]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=self.errors,
        )
