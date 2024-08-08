"""Telegram client entry config flow."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any

from telethon import TelegramClient
from telethon.errors import (
    AccessTokenExpiredError,
    AccessTokenInvalidError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
)
from telethon.errors.rpcerrorlist import FloodWaitError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CLIENT_PARAMS,
    CLIENT_TYPE_USER,
    CONF_API_HASH,
    CONF_API_ID,
    CONF_CLIENT_TYPE,
    CONF_OTP,
    CONF_PHONE,
    CONF_SESSION_ID,
    CONF_TOKEN,
    DOMAIN,
    KEY_ENTRY_ID,
)
from .options_flow import TelegramClientOptionsFlow
from .schemas import (
    STEP_API_DATA_SCHEMA,
    STEP_OTP_DATA_SCHEMA,
    STEP_PHONE_DATA_SCHEMA,
    step_password_data_schema,
    step_token_data_schema,
)


class TelegramClientConfigFlow(ConfigFlow, domain=DOMAIN):
    """Telegram client entry config flow."""

    VERSION = 1
    _api_hash: str
    _api_id: str
    _client: TelegramClient
    _config_entry: ConfigEntry
    _password: str = ""
    _phone: str = ""
    _phone_code_hash: str
    _session: str
    _token: str = ""
    _type: str

    def _create_client(self) -> TelegramClient:
        """Create Telegram client instance."""
        path = Path(self.hass.config.path(STORAGE_DIR, DOMAIN))
        path.mkdir(parents=True, exist_ok=True)
        path = path.joinpath(
            f"{re.sub(r'\D', '', self._phone) if self._type == CLIENT_TYPE_USER else self._token.split(":")[0]}.session"
        )
        return TelegramClient(
            path,
            self._api_id,
            self._api_hash,
            **CLIENT_PARAMS,
        )

    def _get_config_entry(self) -> ConfigEntry | None:
        """Get config entry."""
        entry_id = self.context.get(KEY_ENTRY_ID)
        return self.hass.config_entries.async_get_entry(entry_id) if entry_id else None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create Telegram client options flow."""
        return TelegramClientOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of API parameters step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._session = self.flow_id
            self._api_id = user_input[CONF_API_ID]
            self._api_hash = user_input[CONF_API_HASH]
            self._type = user_input[CONF_CLIENT_TYPE]
            return (
                await self.async_step_phone()
                if self._type == CLIENT_TYPE_USER
                else await self.async_step_token()
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_API_DATA_SCHEMA, errors=errors
        )

    async def async_step_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of phone number step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._phone = user_input[CONF_PHONE]
            self._client = self._create_client()
            return await self.async_step_otp()

        return self.async_show_form(
            step_id=CONF_PHONE, data_schema=STEP_PHONE_DATA_SCHEMA, errors=errors
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of bot token step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._token = user_input[CONF_TOKEN]
            self._client = self._create_client()
            try:
                await self._client.start(bot_token=self._token)
                await self._client.disconnect()
                return await self.async_finish()
            except (AccessTokenExpiredError, AccessTokenInvalidError) as err:
                await self._client.log_out()
                errors[CONF_TOKEN] = str(err)

        entry = self._get_config_entry()
        return self.async_show_form(
            step_id=CONF_TOKEN,
            data_schema=step_token_data_schema(
                entry.data[CONF_TOKEN] if entry else None
            ),
            errors=errors,
        )

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of OTP step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._client.connect()
                await self._client.sign_in(
                    phone=self._phone,
                    code=user_input[CONF_OTP],
                    phone_code_hash=self._phone_code_hash,
                )
                self._client.disconnect()
                return await self.async_finish()
            except SessionPasswordNeededError:
                self._client.disconnect()
                return await self.async_step_password()
            except PhoneCodeExpiredError as err:
                errors[CONF_OTP] = str(err)

        try:
            await self._client.connect()
            result = await self._client.send_code_request(self._phone)
            self._phone_code_hash = result.phone_code_hash
        except (FloodWaitError, Exception) as err:
            return self.async_abort(reason=str(err))
        finally:
            await self._client.disconnect()

        return self.async_show_form(
            step_id=CONF_OTP, data_schema=STEP_OTP_DATA_SCHEMA, errors=errors
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle input of password step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            try:
                await self._client.connect()
                await self._client.sign_in(password=self._password)
                await self._client.disconnect()
                return await self.async_finish()
            except PasswordHashInvalidError:
                await self._client.disconnect()
                errors[CONF_PASSWORD] = "invalid_auth"

        entry = self._get_config_entry()
        return self.async_show_form(
            step_id=CONF_PASSWORD,
            data_schema=step_password_data_schema(
                default_password=entry.data.get(CONF_PASSWORD) if entry else None
            ),
            errors=errors,
            last_step=True,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-auth step."""
        self._session = entry_data.get(CONF_SESSION_ID, "")
        self._api_id = entry_data.get(CONF_API_ID, "")
        self._api_hash = entry_data.get(CONF_API_HASH, "")
        self._type = entry_data.get(CONF_CLIENT_TYPE, CLIENT_TYPE_USER)
        self._phone = entry_data.get(CONF_PHONE, "")

        if self._type == CLIENT_TYPE_USER:
            self._client = self._create_client()
            return await self.async_step_reauth_confirm()
        return await self.async_step_token()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth completion step."""
        if user_input is not None:
            return await self.async_step_otp()

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({})
        )

    async def async_finish(self) -> ConfigFlowResult:
        """Handle Telegram client entry creation."""
        data = {
            CONF_SESSION_ID: self._session,
            CONF_API_ID: self._api_id,
            CONF_API_HASH: self._api_hash,
            CONF_CLIENT_TYPE: self._type,
            CONF_PHONE: self._phone,
            CONF_TOKEN: self._token,
            CONF_PASSWORD: self._password,
        }
        if self.context["source"] == "reauth":
            if reauth_config_entry := self.hass.config_entries.async_get_entry(
                self.context[KEY_ENTRY_ID]
            ):
                self.hass.config_entries.async_update_entry(
                    reauth_config_entry, data=data
                )
                await self.hass.config_entries.async_reload(
                    reauth_config_entry.entry_id
                )
            return self.async_abort(reason="reauth_successful")
        try:
            if self._type == CLIENT_TYPE_USER:
                await self._client.start(phone=self._phone)
            else:
                await self._client.start(bot_token=self._token)
            me = await self._client.get_me()
        finally:
            await self._client.disconnect()
        unique_id = (
            f"@{me.username}" or self._phone
            if self._type == CLIENT_TYPE_USER
            else f"@{me.username}"
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"Telegam {self._type} ({unique_id})", data=data
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
