"""Config flow to configure Life360 integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from life360 import Life360
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_AUTHORIZATION,
    CONF_DRIVING_SPEED,
    CONF_MAX_GPS_ACCURACY,
    CONF_PREFIX,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_SEC,
    DOMAIN,
    LOGGER,
    OPTIONS,
    SHOW_DRIVING,
)
from .helpers import (
    AccountData,
    get_life360_api,
    get_life360_authorization,
    init_integ_data,
)


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

    VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self._api: Life360 | None = None
        self._username: str | vol.UNDEFINED = vol.UNDEFINED
        self._password: str | vol.UNDEFINED = vol.UNDEFINED
        self._options: dict[str, Any] = {}
        self._reauth_entry: ConfigEntry | None = None
        self._first_reauth_confirm = True

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> Life360OptionsFlow:
        """Get the options flow for this handler."""
        return Life360OptionsFlow(config_entry)

    async def _async_verify(self, step_id: str) -> FlowResult:
        """Attempt to authorize the provided credentials."""

        assert self._api
        assert self._username
        assert self._password

        errors: dict[str, str] = {}
        authorization = await get_life360_authorization(
            self.hass, self._api, self._username, self._password, errors
        )
        if errors:
            if step_id == "user":
                schema = account_schema(
                    self._username, self._password
                ) | _account_options_schema(self._options)
            else:
                # Don't show current password the first time we prompt for password
                # since this will happen asynchronously. However, once the user enters a
                # password, we can show it in case it's not valid to make it easier to
                # enter a long, complicated password.
                pwd = vol.UNDEFINED if self._first_reauth_confirm else self._password
                self._first_reauth_confirm = False
                schema = password_schema(pwd)
            return self.async_show_form(
                step_id=step_id, data_schema=vol.Schema(schema), errors=errors
            )

        data = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            CONF_AUTHORIZATION: authorization,
        }

        if self._reauth_entry:
            LOGGER.info("Reauthorization successful")
            self.hass.config_entries.async_update_entry(self._reauth_entry, data=data)
            if self._reauth_entry.state == ConfigEntryState.LOADED:
                # Config entry reload should not be necessary. Restarting coordinator's
                # scheduled refreshes should be sufficient since Life360 api object is
                # valid again after successful reauthorization.
                coordinator = self.hass.data[DOMAIN]["accounts"][self.unique_id][
                    "coordinator"
                ]
                self.hass.async_create_task(coordinator.async_request_refresh())
            else:
                # Config entry never got completely loaded, so do a full reload.
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                )
            return self.async_abort(reason="reauth_successful")

        init_integ_data(self.hass)
        self.hass.data[DOMAIN]["accounts"][cast(str, self.unique_id)] = AccountData(
            api=self._api
        )
        return self.async_create_entry(
            title=cast(str, self.unique_id), data=data, options=self._options
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a config flow initiated by the user."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    account_schema() | _account_options_schema(self._options)
                ),
            )

        self._options = _extract_account_options(user_input)

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        await self.async_set_unique_id(self._username.lower())
        self._abort_if_unique_id_configured()

        if not self._api:
            self._api = get_life360_api()

        return await self._async_verify("user")

    async def async_step_reauth(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle reauthorization."""
        self._username = user_input[CONF_USERNAME]
        self._api = self.hass.data[DOMAIN]["accounts"][self.unique_id]["api"]
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        # Always start with current credentials since they may still be valid and a
        # simple reauthorization will be successful.
        return await self.async_step_reauth_confirm(user_input)

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
            # If prefix has changed then tell __init__.async_update_options() to remove
            # and re-add config entry.
            self.hass.data[DOMAIN]["accounts"][self.config_entry.unique_id][
                "re_add_entry"
            ] = new_options.get(CONF_PREFIX) != options.get(CONF_PREFIX)
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(_account_options_schema(options))
        )


def _account_options_schema(options: Mapping[str, Any]) -> dict[vol.Marker, Any]:
    """Create schema for account options form."""
    def_use_prefix = CONF_PREFIX in options
    def_prefix = options.get(CONF_PREFIX, vol.UNDEFINED)
    def_limit_gps_acc = CONF_MAX_GPS_ACCURACY in options
    def_max_gps = options.get(CONF_MAX_GPS_ACCURACY, vol.UNDEFINED)
    def_set_drive_speed = CONF_DRIVING_SPEED in options
    def_speed = options.get(CONF_DRIVING_SPEED, vol.UNDEFINED)
    def_scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SEC)
    def_show_driving = options.get(SHOW_DRIVING, vol.UNDEFINED)

    return {
        vol.Required("use_prefix", default=def_use_prefix): bool,
        vol.Optional(CONF_PREFIX, default=def_prefix): str,
        vol.Required("limit_gps_acc", default=def_limit_gps_acc): bool,
        vol.Optional(CONF_MAX_GPS_ACCURACY, default=def_max_gps): vol.Coerce(float),
        vol.Required("set_drive_speed", default=def_set_drive_speed): bool,
        vol.Optional(CONF_DRIVING_SPEED, default=def_speed): vol.Coerce(float),
        vol.Optional(CONF_SCAN_INTERVAL, default=def_scan_interval): vol.Coerce(float),
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
                CONF_PREFIX: "use_prefix",
                CONF_MAX_GPS_ACCURACY: "limmit_gps_acc",
                CONF_DRIVING_SPEED: "set_drive_speed",
            }.get(key),
            True,
        )
        if incl and value is not None:
            result[key] = value

    return result
