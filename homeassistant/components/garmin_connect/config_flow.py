"""Config flow for Garmin Connect integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError
from ha_garmin import (
    GarminAuth,
    GarminAuthError,
    GarminClient,
    GarminConnectError,
    GarminMFARequired,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_CLIENT_ID, CONF_REFRESH_TOKEN, CONF_TOKEN, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_MFA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("mfa_code"): str,
    }
)


class GarminConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Garmin Connect."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._auth: GarminAuth | None = None
        self._username: str | None = None
        self._is_cn: bool = False

    def _token_data(self) -> dict[str, Any]:
        """Return token data from current auth state."""
        assert self._auth is not None
        return {
            CONF_TOKEN: self._auth.di_token,
            CONF_REFRESH_TOKEN: self._auth.di_refresh_token,
            CONF_CLIENT_ID: self._auth.di_client_id,
        }

    async def _async_login(self, username: str, password: str) -> None:
        """Run Garmin login in the executor."""
        assert self._auth is not None
        await self.hass.async_add_executor_job(
            self._auth.login,
            username,
            password,
        )

    async def _async_complete_mfa(self, mfa_code: str) -> None:
        """Run Garmin MFA completion in the executor."""
        assert self._auth is not None
        await self.hass.async_add_executor_job(
            self._auth.complete_mfa,
            mfa_code,
        )

    async def _async_finish_reauth(self) -> ConfigFlowResult:
        """Update tokens on the existing entry and reload it."""
        entry = self._get_reauth_entry()
        self.hass.config_entries.async_update_entry(entry, data=self._token_data())
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    async def _async_create_new_entry(self) -> ConfigFlowResult:
        """Finalize a new config entry after successful authentication."""
        assert self._auth is not None
        unique_id = self._username
        try:
            client = GarminClient(self._auth, is_cn=self._is_cn)
            profile = await client.get_user_profile()
            unique_id = str(profile.profile_id)
        except GarminConnectError, ClientError:
            pass
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._username or "Garmin Connect",
            data=self._token_data(),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._is_cn = self.hass.config.country == "CN"
            self._auth = GarminAuth(is_cn=self._is_cn)

            try:
                await self._async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except GarminMFARequired:
                return await self.async_step_mfa()
            except GarminAuthError:
                errors["base"] = "invalid_auth"
            except GarminConnectError:
                errors["base"] = "unknown"
            else:
                return await self._async_create_new_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle MFA step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            assert self._auth is not None

            try:
                await self._async_complete_mfa(user_input["mfa_code"])
            except GarminAuthError:
                errors["base"] = "invalid_mfa"
            except GarminConnectError:
                errors["base"] = "unknown"
            else:
                if self.source == SOURCE_REAUTH:
                    return await self._async_finish_reauth()
                return await self._async_create_new_entry()

        return self.async_show_form(
            step_id="mfa",
            data_schema=STEP_MFA_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._is_cn = self.hass.config.country == "CN"
            self._auth = GarminAuth(is_cn=self._is_cn)

            try:
                await self._async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except GarminMFARequired:
                return await self.async_step_mfa()
            except GarminAuthError:
                errors["base"] = "invalid_auth"
            except GarminConnectError:
                errors["base"] = "unknown"
            else:
                return await self._async_finish_reauth()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._is_cn = self.hass.config.country == "CN"
            self._auth = GarminAuth(is_cn=self._is_cn)

            try:
                await self._async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except GarminMFARequired:
                return await self.async_step_mfa()
            except GarminAuthError:
                errors["base"] = "invalid_auth"
            except GarminConnectError:
                errors["base"] = "unknown"
            else:
                # Update the existing entry
                entry = self._get_reconfigure_entry()
                self.hass.config_entries.async_update_entry(
                    entry, data=self._token_data()
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
