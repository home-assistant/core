"""Config flow for Xthings Cloud."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .api import XthingsCloudApiClient, XthingsCloudAuthError, XthingsCloudApiError
from .const import CONF_EMAIL, CONF_PASSWORD, CONF_REFRESH_TOKEN, CONF_REMOTE_ACCESS, CONF_TOKEN, DOMAIN

CONF_VERIFICATION_CODE = "verification_code"

# API error code to translation key mapping
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

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> XthingsCloudOptionsFlow:
        """Get the options flow handler."""
        return XthingsCloudOptionsFlow(config_entry)

    def __init__(self) -> None:
        self._email: str | None = None
        self._password: str | None = None
        self._instance_id: str | None = None
        self._2fa_type: int = 0  # 1=email, 2=phone
        self._reauth_entry: ConfigEntry | None = None

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

    def _create_entry_data(self, token_data: dict[str, Any]) -> dict[str, Any]:
        return {
            CONF_EMAIL: self._email,
            CONF_PASSWORD: self._password,
            CONF_TOKEN: token_data["token"],
            CONF_REFRESH_TOKEN: token_data["refresh_token"],
        }

    def _get_2fa_step(self) -> str:
        """Return the 2FA step id based on 2fa type."""
        return "2fa_phone" if self._2fa_type == 2 else "2fa_email"

    # --- User login flow ---

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
                errors["base"] = "unknown"
            else:
                if token_data.get("2fa"):
                    self._2fa_type = token_data["2fa"]
                    step = self._get_2fa_step()
                    return await getattr(self, f"async_step_{step}")()
                await self.async_set_unique_id(self._email)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._email, data=self._create_entry_data(token_data),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    # --- 2FA steps (email / phone) ---

    async def _async_handle_2fa(
        self, step_id: str, user_input: dict[str, Any] | None,
        on_success_create: bool = True,
    ) -> FlowResult:
        """Shared 2FA verification handler."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input[CONF_VERIFICATION_CODE]
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
                        title=self._email, data=self._create_entry_data(token_data),
                    )
                else:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=self._create_entry_data(token_data),
                    )
                    await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema({
                vol.Required(CONF_VERIFICATION_CODE): str,
            }),
            errors=errors,
            description_placeholders={"email": self._email},
        )

    async def async_step_2fa_email(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle 2FA via email verification code."""
        return await self._async_handle_2fa("2fa_email", user_input)

    async def async_step_2fa_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle 2FA via phone verification code."""
        return await self._async_handle_2fa("2fa_phone", user_input)

    # --- Reauth flow ---

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Handle re-authentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._email = entry_data.get(CONF_EMAIL)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication confirm step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            try:
                token_data = await self._async_try_login(
                    self._email, self._password,
                )
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
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=self._create_entry_data(token_data),
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        default_email = ""
        if self._reauth_entry:
            default_email = self._reauth_entry.data.get(CONF_EMAIL, "")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL, default=default_email): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_reauth_2fa_email(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle 2FA via email during re-authentication."""
        return await self._async_handle_2fa("reauth_2fa_email", user_input, on_success_create=False)

    async def async_step_reauth_2fa_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle 2FA via phone during re-authentication."""
        return await self._async_handle_2fa("reauth_2fa_phone", user_input, on_success_create=False)


class XthingsCloudOptionsFlow(OptionsFlow):
    """Xthings Cloud options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_REMOTE_ACCESS,
                    default=self._config_entry.options.get(CONF_REMOTE_ACCESS, False),
                ): bool,
            }),
        )
