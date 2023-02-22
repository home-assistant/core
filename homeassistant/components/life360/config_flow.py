"""Config flow to configure Life360 integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from life360 import Life360, Life360Error, LoginError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    COMM_TIMEOUT,
    CONF_AUTHORIZATION,
    CONF_DRIVING_SPEED,
    CONF_MAX_GPS_ACCURACY,
    DEFAULT_OPTIONS,
    DOMAIN,
    LOGGER,
    OPTIONS,
    SHOW_DRIVING,
)

LIMIT_GPS_ACC = "limit_gps_acc"
SET_DRIVE_SPEED = "set_drive_speed"


def account_schema(
    def_username: str | vol.UNDEFINED = vol.UNDEFINED,
    def_password: str | vol.UNDEFINED = vol.UNDEFINED,
) -> dict[vol.Marker, Any]:
    """Return schema for an account with optional default values."""
    return {
        vol.Required(CONF_USERNAME, default=def_username): cv.string,
        vol.Required(CONF_PASSWORD, default=def_password): cv.string,
    }


def password_schema(
    def_password: str | vol.UNDEFINED = vol.UNDEFINED,
) -> dict[vol.Marker, Any]:
    """Return schema for a password with optional default value."""
    return {vol.Required(CONF_PASSWORD, default=def_password): cv.string}


class Life360ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Life360 integration config flow."""

    VERSION = 1
    _api: Life360 | None = None
    _username: str | vol.UNDEFINED = vol.UNDEFINED
    _password: str | vol.UNDEFINED = vol.UNDEFINED
    _reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> Life360OptionsFlow:
        """Get the options flow for this handler."""
        return Life360OptionsFlow(config_entry)

    async def _async_verify(self, step_id: str) -> FlowResult:
        """Attempt to authorize the provided credentials."""
        if not self._api:
            self._api = Life360(
                session=async_get_clientsession(self.hass), timeout=COMM_TIMEOUT
            )
        errors: dict[str, str] = {}
        try:
            authorization = await self._api.get_authorization(
                self._username, self._password
            )
        except LoginError as exc:
            LOGGER.debug("Login error: %s", exc)
            errors["base"] = "invalid_auth"
        except Life360Error as exc:
            LOGGER.debug("Unexpected error communicating with Life360 server: %s", exc)
            errors["base"] = "cannot_connect"
        if errors:
            if step_id == "user":
                schema = account_schema(self._username, self._password)
            else:
                schema = password_schema(self._password)
            return self.async_show_form(
                step_id=step_id, data_schema=vol.Schema(schema), errors=errors
            )

        data = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            CONF_AUTHORIZATION: authorization,
        }

        if self._reauth_entry:
            LOGGER.debug("Reauthorization successful")
            self.hass.config_entries.async_update_entry(self._reauth_entry, data=data)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=cast(str, self.unique_id), data=data, options=DEFAULT_OPTIONS
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a config flow initiated by the user."""
        if not user_input:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(account_schema())
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        await self.async_set_unique_id(self._username.lower())
        self._abort_if_unique_id_configured()

        return await self._async_verify("user")

    async def async_step_reauth(self, data: Mapping[str, Any]) -> FlowResult:
        """Handle reauthorization."""
        self._username = data[CONF_USERNAME]
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        # Always start with current credentials since they may still be valid and a
        # simple reauthorization will be successful.
        return await self.async_step_reauth_confirm(dict(data))

    async def async_step_reauth_confirm(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle reauthorization completion."""
        self._password = user_input[CONF_PASSWORD]
        return await self._async_verify("reauth_confirm")


class Life360OptionsFlow(OptionsFlow):
    """Life360 integration options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle account options."""
        options = self.config_entry.options

        if user_input is not None:
            new_options = _extract_account_options(user_input)
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(_account_options_schema(options))
        )


def _account_options_schema(options: Mapping[str, Any]) -> dict[vol.Marker, Any]:
    """Create schema for account options form."""
    def_limit_gps_acc = options[CONF_MAX_GPS_ACCURACY] is not None
    def_max_gps = options[CONF_MAX_GPS_ACCURACY] or vol.UNDEFINED
    def_set_drive_speed = options[CONF_DRIVING_SPEED] is not None
    def_speed = options[CONF_DRIVING_SPEED] or vol.UNDEFINED
    def_show_driving = options[SHOW_DRIVING]

    return {
        vol.Required(LIMIT_GPS_ACC, default=def_limit_gps_acc): bool,
        vol.Optional(CONF_MAX_GPS_ACCURACY, default=def_max_gps): vol.Coerce(float),
        vol.Required(SET_DRIVE_SPEED, default=def_set_drive_speed): bool,
        vol.Optional(CONF_DRIVING_SPEED, default=def_speed): vol.Coerce(float),
        vol.Optional(SHOW_DRIVING, default=def_show_driving): bool,
    }


def _extract_account_options(user_input: dict) -> dict[str, Any]:
    """Remove options from user input and return as a separate dict."""
    result = {}

    for key in OPTIONS:
        value = user_input.pop(key, None)
        # Was "include" checkbox (if there was one) corresponding to option key True
        # (meaning option should be included)?
        incl = user_input.pop(
            {
                CONF_MAX_GPS_ACCURACY: LIMIT_GPS_ACC,
                CONF_DRIVING_SPEED: SET_DRIVE_SPEED,
            }.get(key),
            True,
        )
        result[key] = value if incl else None

    return result
