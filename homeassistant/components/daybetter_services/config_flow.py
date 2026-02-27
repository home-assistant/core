"""Config flow for DayBetter Services integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from daybetter_python import APIError, AuthenticationError, DayBetterClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TOKEN, CONF_USER_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class DayBetterServicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DayBetter Services."""

    VERSION = 1

    _reauth_entry: ConfigEntry | None
    _reauth_user_code: str

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry = None
        self._reauth_user_code = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        default_user_code = user_input[CONF_USER_CODE] if user_input else ""
        return await self._async_handle_step(
            user_input,
            step_id="user",
            default_user_code=default_user_code,
            is_reauth=False,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle the start of the re-authentication flow."""
        self._reauth_entry = self._get_reauth_entry()
        self._reauth_user_code = entry_data[CONF_USER_CODE]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the re-authentication confirmation step."""
        return await self._async_handle_step(
            user_input,
            step_id="reauth_confirm",
            default_user_code=self._reauth_user_code,
            is_reauth=True,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure flow to update user code."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                data = await self._async_validate_credentials(
                    user_input[CONF_USER_CODE]
                )
            except InvalidCode:
                errors["base"] = "invalid_code"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during DayBetter config flow")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data=data)

        schema = self.add_suggested_values_to_schema(
            vol.Schema({vol.Required(CONF_USER_CODE): str}),
            entry.data,
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )

    async def _async_handle_step(
        self,
        user_input: dict[str, Any] | None,
        *,
        step_id: str,
        default_user_code: str,
        is_reauth: bool,
    ) -> ConfigFlowResult:
        """Validate user input and either create or update the entry."""

        errors: dict[str, str] = {}
        current_user_code = default_user_code

        if user_input is not None:
            current_user_code = user_input[CONF_USER_CODE]
            try:
                data = await self._async_validate_credentials(current_user_code)
            except InvalidCode:
                errors["base"] = "invalid_code"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during DayBetter config flow")
                errors["base"] = "unknown"
            else:
                if is_reauth:
                    entry = self._reauth_entry
                    assert entry is not None
                    return self.async_update_reload_and_abort(entry, data=data)
                return self.async_create_entry(title="DayBetter Services", data=data)

        schema = self.add_suggested_values_to_schema(
            vol.Schema({vol.Required(CONF_USER_CODE): str}),
            {CONF_USER_CODE: current_user_code},
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
        )

    async def _async_validate_credentials(self, user_code: str) -> dict[str, str]:
        """Validate user code and return entry data."""
        session = async_get_clientsession(self.hass)
        client = DayBetterClient(token="", session=session)
        client_with_token: DayBetterClient | None = None
        try:
            try:
                integrate_result = await client.integrate(user_code)
            except (AuthenticationError, APIError) as err:
                raise CannotConnect from err

            if integrate_result.get("code") != 1 or "hassCodeToken" not in (
                integrate_result.get("data") or {}
            ):
                raise InvalidCode

            token = integrate_result["data"]["hassCodeToken"]

            client_with_token = DayBetterClient(token=token, session=session)
            await client_with_token.fetch_devices()
            await client_with_token.fetch_pids()
        except (AuthenticationError, APIError) as err:
            raise CannotConnect from err

        return {
            CONF_USER_CODE: user_code,
            CONF_TOKEN: token,
        }


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidCode(HomeAssistantError):
    """Error to indicate invalid user code."""
