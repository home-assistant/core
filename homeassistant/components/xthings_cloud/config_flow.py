"""Config flow for Xthings Cloud."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from ha_xthings_cloud import XthingsCloudApiClient, XthingsCloudAuthError, XthingsCloudApiError
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_REFRESH_TOKEN, CONF_TOKEN, DOMAIN, LOGGER

CONF_VERIFICATION_CODE = "verification_code"

ERROR_CODE_MAP: dict[int, str] = {
    20001: "token_invalid",
    21001: "email_empty",
    21002: "email_invalid",
    21004: "email_not_found",
    21005: "email_verify_error",
    21011: "password_empty",
    21014: "password_wrong",
    21021: "user_disabled",
    21022: "user_not_logged_in",
    21023: "user_not_activated",
    20011: "token_invalid",
    20012: "token_expired",
    22001: "device_not_found",
    22003: "device_offline",
}


def _error_from_exception(err: XthingsCloudApiError) -> str:
    """Return translation key from error code."""
    return ERROR_CODE_MAP.get(err.code, "unknown")


class XthingsCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Xthings Cloud config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._email: str | None = None
        self._password: str | None = None
        self._instance_id: str | None = None
        self._2fa_type: int = 0

    async def _async_try_login(
        self, email: str, password: str,
        verification_code: str | None = None,
    ) -> dict[str, Any]:
        """Attempt login, return token data or 2fa info."""
        if not self._instance_id:
            self._instance_id = await async_get_instance_id(self.hass)
        session = async_get_clientsession(self.hass)
        client = XthingsCloudApiClient(session)
        return await client.async_login(
            email, password, client_id=self._instance_id,
            verification_code=verification_code,
        )

    def _create_entry_data(self, token_data: dict[str, Any]) -> dict[str, str]:
        assert self._email is not None
        return {
            CONF_EMAIL: self._email,
            CONF_TOKEN: token_data["token"],
            CONF_REFRESH_TOKEN: token_data["refresh_token"],
        }

    def _get_2fa_step(self) -> str:
        return "2fa_phone" if self._2fa_type == 2 else "2fa_email"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user input step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            try:
                token_data = await self._async_try_login(self._email, self._password)
            except XthingsCloudAuthError as err:
                errors["base"] = _error_from_exception(err)
            except XthingsCloudApiError as err:
                errors["base"] = _error_from_exception(err) if err.code else "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error during login")
                errors["base"] = "unknown"
            else:
                if token_data.get("2fa"):
                    self._2fa_type = token_data["2fa"]
                    step = self._get_2fa_step()
                    return await getattr(self, f"async_step_{step}")()
                await self.async_set_unique_id(self._email)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._email or "",
                    data=self._create_entry_data(token_data),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def _async_handle_2fa(
        self, step_id: str, user_input: dict[str, Any] | None,
        on_success_create: bool = True,
    ) -> ConfigFlowResult:
        """Shared 2FA verification handler."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input[CONF_VERIFICATION_CODE]
            assert self._email is not None
            assert self._password is not None
            try:
                token_data = await self._async_try_login(
                    self._email, self._password,
                    verification_code=code,
                )
            except XthingsCloudAuthError as err:
                errors["base"] = _error_from_exception(err)
            except XthingsCloudApiError as err:
                errors["base"] = _error_from_exception(err) if err.code else "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                if token_data.get("2fa"):
                    errors["base"] = "invalid_verification_code"
                elif on_success_create:
                    await self.async_set_unique_id(self._email)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=self._email or "",
                        data=self._create_entry_data(token_data),
                    )
                else:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data=self._create_entry_data(token_data),
                    )

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({
                vol.Required(CONF_VERIFICATION_CODE): str,
            }),
            errors=errors,
            description_placeholders={"email": self._email or ""},
        )

    async def async_step_2fa_email(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle 2FA via email verification code."""
        return await self._async_handle_2fa("2fa_email", user_input)

    async def async_step_2fa_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle 2FA via phone verification code."""
        return await self._async_handle_2fa("2fa_phone", user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        self._email = entry_data.get(CONF_EMAIL)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirm step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            try:
                token_data = await self._async_try_login(self._email, self._password)
            except XthingsCloudAuthError as err:
                errors["base"] = _error_from_exception(err)
            except XthingsCloudApiError as err:
                errors["base"] = _error_from_exception(err) if err.code else "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                if token_data.get("2fa"):
                    self._2fa_type = token_data["2fa"]
                    step = f"reauth_{self._get_2fa_step()}"
                    return await getattr(self, f"async_step_{step}")()
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data=self._create_entry_data(token_data),
                )

        reauth_entry = self._get_reauth_entry()
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL, default=reauth_entry.data.get(CONF_EMAIL, "")): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_reauth_2fa_email(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle 2FA via email during re-authentication."""
        return await self._async_handle_2fa("reauth_2fa_email", user_input, on_success_create=False)

    async def async_step_reauth_2fa_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle 2FA via phone during re-authentication."""
        return await self._async_handle_2fa("reauth_2fa_phone", user_input, on_success_create=False)
