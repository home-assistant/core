"""Config flow for Alexa Devices integration."""

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any, override

from aioamazondevices.api import AmazonEchoApi
from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
)
from aioamazondevices.structures import AmazonSaveDataConfig
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv

from .const import CONF_LOGIN_DATA, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CODE): cv.string,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CODE): cv.string,
    }
)
STEP_RECONFIGURE = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CODE): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    session = aiohttp_client.async_create_clientsession(hass)
    api = AmazonEchoApi(
        session,
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        save_data=AmazonSaveDataConfig(
            path=Path(hass.config.path(DOMAIN)),
        ),
    )

    return await api.login.login_mode_interactive(data[CONF_CODE])


class AmazonDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Alexa Devices."""

    VERSION = 1
    MINOR_VERSION = 3

    _login_data: dict[str, Any]

    def __init__(self) -> None:
        """Initialize a new AmazonDevicesConfigFlow."""
        self._login_task: asyncio.Task[dict[str, Any]] | None = None
        self._login_errors: dict[str, str] = {}
        self._login_result: dict[str, Any] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._login_data = user_input
            return await self.async_step_login()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=self._login_errors,
        )

    async def async_step_login(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Log in and scan for devices, showing progress to the user."""
        if (login_task := self._login_task) and login_task.done():
            self._login_errors = {}
            try:
                self._login_result = login_task.result()
            except CannotConnect:
                self._login_errors = {"base": "cannot_connect"}
            except CannotAuthenticate:
                self._login_errors = {"base": "invalid_auth"}
            except CannotRetrieveData:
                self._login_errors = {"base": "cannot_retrieve_data"}
            finally:
                self._login_task = None

            return self.async_show_progress_done(
                next_step_id="user" if self._login_errors else "login_done"
            )

        if self._login_task is None:
            self._login_task = self.hass.async_create_task(
                validate_input(self.hass, self._login_data)
            )

        return self.async_show_progress(
            step_id="login",
            progress_action="login",
            progress_task=self._login_task,
        )

    async def async_step_login_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the config entry after a successful login."""
        await self.async_set_unique_id(self._login_result["customer_info"]["user_id"])
        self._abort_if_unique_id_configured()
        self._login_data.pop(CONF_CODE)
        return self.async_create_entry(
            title=self._login_data[CONF_USERNAME],
            data=self._login_data | {CONF_LOGIN_DATA: self._login_result},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow."""
        self.context["title_placeholders"] = {CONF_USERNAME: entry_data[CONF_USERNAME]}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirm."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        entry_data = reauth_entry.data

        if user_input is not None:
            try:
                data = await validate_input(
                    self.hass, {**reauth_entry.data, **user_input}
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CannotAuthenticate:
                errors["base"] = "invalid_auth"
            except CannotRetrieveData:
                errors["base"] = "cannot_retrieve_data"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        CONF_USERNAME: entry_data[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_CODE: user_input[CONF_CODE],
                        CONF_LOGIN_DATA: data,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_USERNAME: entry_data[CONF_USERNAME]},
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the device."""
        reconfigure_entry = self._get_reconfigure_entry()
        if not user_input:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=STEP_RECONFIGURE,
            )

        updated_password = user_input[CONF_PASSWORD]

        self._async_abort_entries_match(
            {CONF_USERNAME: reconfigure_entry.data[CONF_USERNAME]}
        )

        errors: dict[str, str] = {}

        try:
            data = await validate_input(
                self.hass, {**reconfigure_entry.data, **user_input}
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except CannotAuthenticate:
            errors["base"] = "invalid_auth"
        except CannotRetrieveData:
            errors["base"] = "cannot_retrieve_data"
        else:
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                data_updates={
                    CONF_PASSWORD: updated_password,
                    CONF_LOGIN_DATA: data,
                },
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_RECONFIGURE,
            errors=errors,
        )
