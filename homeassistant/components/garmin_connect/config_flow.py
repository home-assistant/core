"""Config flow for Garmin Connect integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiogarmin import GarminAuth, GarminAuthError, GarminMFARequired
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_OAUTH1_TOKEN,
    CONF_OAUTH2_TOKEN,
    DOMAIN,
)

type GarminConnectConfigEntry = ConfigEntry

_LOGGER = logging.getLogger(__name__)

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


    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            session = async_get_clientsession(self.hass)
            self._auth = GarminAuth(session)

            try:
                result = await self._auth.login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )

                # Login successful, create entry
                await self.async_set_unique_id(self._username)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._username,
                    data={
                        CONF_OAUTH1_TOKEN: result.oauth1_token,
                        CONF_OAUTH2_TOKEN: result.oauth2_token,
                    },
                )

            except GarminMFARequired:
                # MFA required, show MFA step
                return await self.async_step_mfa()

            except GarminAuthError as err:
                _LOGGER.error("Authentication failed: %s", err)
                errors["base"] = "invalid_auth"

            except Exception:
                _LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"

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
            if self._auth is None:
                return self.async_abort(reason="mfa_session_expired")

            try:
                result = await self._auth.complete_mfa(user_input["mfa_code"])

                await self.async_set_unique_id(self._username)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._username or "Garmin Connect",
                    data={
                        CONF_OAUTH1_TOKEN: result.oauth1_token,
                        CONF_OAUTH2_TOKEN: result.oauth2_token,
                    },
                )

            except GarminAuthError as err:
                _LOGGER.error("MFA verification failed: %s", err)
                errors["base"] = "invalid_mfa"

            except Exception:
                _LOGGER.exception("Unexpected error during MFA")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="mfa",
            data_schema=STEP_MFA_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth triggered by expired tokens."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            self._auth = GarminAuth(session)
            self._username = user_input[CONF_USERNAME]

            try:
                result = await self._auth.login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )

                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data={
                        CONF_OAUTH1_TOKEN: result.oauth1_token,
                        CONF_OAUTH2_TOKEN: result.oauth2_token,
                    },
                )

            except GarminMFARequired:
                return await self.async_step_mfa()

            except GarminAuthError as err:
                _LOGGER.error("Reauth failed: %s", err)
                errors["base"] = "invalid_auth"

            except Exception:
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            self._auth = GarminAuth(session)
            self._username = user_input[CONF_USERNAME]

            try:
                result = await self._auth.login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        CONF_OAUTH1_TOKEN: result.oauth1_token,
                        CONF_OAUTH2_TOKEN: result.oauth2_token,
                    },
                )

            except GarminMFARequired:
                return await self.async_step_mfa()

            except GarminAuthError as err:
                _LOGGER.error("Reconfigure failed: %s", err)
                errors["base"] = "invalid_auth"

            except Exception:
                _LOGGER.exception("Unexpected error during reconfigure")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

