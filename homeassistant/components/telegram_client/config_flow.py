"""Config flow for Telegram client integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import PasswordHashInvalidError, SessionPasswordNeededError
from telethon.errors.rpcerrorlist import FloodWaitError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_API_HASH,
    CONF_API_ID,
    CONF_OTP,
    CONF_PHONE,
    CONF_SESSION_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_API_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_ID): str,
        vol.Required(CONF_API_HASH): str,
    }
)
STEP_PHONE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE): str,
    }
)
STEP_OTP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OTP): str,
    }
)
STEP_PASSWORD_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class TelegramClientConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Telegram client."""

    VERSION = 1
    _session: str | None = None
    _api_id: str | None = None
    _api_hash: str | None = None
    _phone: str = ""
    _phone_code_hash: str | None = None
    _password: str | None = None

    def create_client(self):
        """Create Telegram client."""
        path = Path(self.hass.config.path(STORAGE_DIR, DOMAIN))
        path.mkdir(parents=True, exist_ok=True)
        path = path.joinpath(f"{self._session}.session")
        return TelegramClient(
            path,
            self._api_id,
            self._api_hash,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle API input."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._session = self.flow_id
            self._api_id = user_input[CONF_API_ID]
            self._api_hash = user_input[CONF_API_HASH]
            return await self.async_step_phone()

        return self.async_show_form(
            step_id="user", data_schema=STEP_API_DATA_SCHEMA, errors=errors
        )

    async def async_step_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle phone number input."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._phone = user_input[CONF_PHONE]
            await self.async_set_unique_id(self._phone)
            self._abort_if_unique_id_configured()
            return await self.async_step_otp()

        return self.async_show_form(
            step_id="phone", data_schema=STEP_PHONE_DATA_SCHEMA, errors=errors
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle OTP input."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = self.create_client()
            try:
                await client.connect()
                await client.sign_in(
                    self._phone,
                    code=user_input[CONF_OTP],
                    phone_code_hash=self._phone_code_hash,
                )
                return await self.async_finish()
            except SessionPasswordNeededError:
                return await self.async_step_password()
            finally:
                await client.disconnect()

        client = self.create_client()
        try:
            await client.connect()
            result = await client.send_code_request(self._phone)
            self._phone_code_hash = result.phone_code_hash
        except (FloodWaitError, Exception) as ex:
            return self.async_abort(reason=str(ex))
        finally:
            await client.disconnect()

        return self.async_show_form(
            step_id="otp", data_schema=STEP_OTP_DATA_SCHEMA, errors=errors
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle password input."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            client = self.create_client()
            try:
                await client.connect()
                await client.sign_in(password=self._password)
                return await self.async_finish()
            except PasswordHashInvalidError:
                errors[CONF_PASSWORD] = "invalid_auth"
            finally:
                await client.disconnect()

        return self.async_show_form(
            step_id="password",
            data_schema=STEP_PASSWORD_DATA_SCHEMA,
            errors=errors,
            last_step=True,
        )

    async def async_finish(self) -> ConfigFlowResult:
        """Handle entry creation."""
        return self.async_create_entry(
            title=self._phone,
            data={
                CONF_SESSION_ID: self._session,
                CONF_API_ID: self._api_id,
                CONF_API_HASH: self._api_hash,
                CONF_PHONE: self._phone,
                CONF_PASSWORD: self._password,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-auth."""
        self._session = self.flow_id
        self._api_id = entry_data[CONF_API_ID]
        self._api_hash = entry_data[CONF_API_HASH]
        self._phone = entry_data[CONF_PHONE]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth completion."""
        if user_input is not None:
            return await self.async_step_otp()

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({})
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
