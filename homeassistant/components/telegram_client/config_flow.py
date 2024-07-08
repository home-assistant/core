"""Config flow for Telegram client integration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.errors import (
    AccessTokenInvalidError,
    PasswordHashInvalidError,
    SessionPasswordNeededError,
)
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
    CONF_TOKEN,
    CONF_TYPE,
    CONF_TYPE_CLIENT,
    DOMAIN,
)
from .schemas import (
    STEP_API_DATA_SCHEMA,
    STEP_OTP_DATA_SCHEMA,
    STEP_PASSWORD_DATA_SCHEMA,
    STEP_PHONE_DATA_SCHEMA,
    STEP_TOKEN_DATA_SCHEMA,
)


class TelegramClientConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Telegram client."""

    VERSION = 1
    _session: str
    _api_id: str
    _api_hash: str
    _type: str
    _phone: str = ""
    _phone_code_hash: str
    _token: str = ""
    _password: str = ""

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
            self._type = user_input[CONF_TYPE]
            return (
                await self.async_step_phone()
                if self._type == CONF_TYPE_CLIENT
                else await self.async_step_token()
            )

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
            step_id=CONF_PHONE, data_schema=STEP_PHONE_DATA_SCHEMA, errors=errors
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle token input."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._token = user_input[CONF_TOKEN]
            await self.async_set_unique_id(self._token.split(":")[0])
            self._abort_if_unique_id_configured()
            client = self.create_client()
            try:
                await client.connect()
                await client.start(bot_token=self._token)
                return await self.async_finish()
            except AccessTokenInvalidError:
                errors[CONF_TOKEN] = "invalid_auth"
            finally:
                await client.disconnect()

        return self.async_show_form(
            step_id=CONF_TOKEN, data_schema=STEP_TOKEN_DATA_SCHEMA, errors=errors
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
        except (FloodWaitError, Exception) as err:
            return self.async_abort(reason=str(err))
        finally:
            await client.disconnect()

        return self.async_show_form(
            step_id=CONF_OTP, data_schema=STEP_OTP_DATA_SCHEMA, errors=errors
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
            step_id=CONF_PASSWORD,
            data_schema=STEP_PASSWORD_DATA_SCHEMA,
            errors=errors,
            last_step=True,
        )

    async def async_finish(self) -> ConfigFlowResult:
        """Handle entry creation."""
        data = {
            CONF_SESSION_ID: self._session,
            CONF_API_ID: self._api_id,
            CONF_API_HASH: self._api_hash,
            CONF_TYPE: self._type,
            CONF_PHONE: self._phone,
            CONF_TOKEN: self._token,
            CONF_PASSWORD: self._password,
        }
        if self.context["source"] == "reauth":
            if reauth_entry := self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            ):
                self.hass.config_entries.async_update_entry(reauth_entry, data=data)
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        unique_id = (
            self._phone if self._type == CONF_TYPE_CLIENT else self._token.split(":")[0]
        )
        return self.async_create_entry(
            title=f"Telegam {self._type} ({unique_id})",
            data=data,
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
