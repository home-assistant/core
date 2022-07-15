"""Config flow for flume integration."""
from collections.abc import Mapping
import logging
import os
from typing import Any

from pyflume import FlumeAuth, FlumeDeviceList
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult

from .const import BASE_TOKEN_FILENAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

# If flume ever implements a login page for oauth
# we can use the oauth2 support built into Home Assistant.
#
# Currently they only implement the token endpoint
#
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
    }
)


def _validate_input(hass: core.HomeAssistant, data: dict, clear_token_file: bool):
    """Validate in the executor."""
    flume_token_full_path = hass.config.path(
        f"{BASE_TOKEN_FILENAME}-{data[CONF_USERNAME]}"
    )
    if clear_token_file and os.path.exists(flume_token_full_path):
        os.unlink(flume_token_full_path)

    return FlumeDeviceList(
        FlumeAuth(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data[CONF_CLIENT_ID],
            data[CONF_CLIENT_SECRET],
            flume_token_file=flume_token_full_path,
        )
    )


async def validate_input(
    hass: core.HomeAssistant, data: dict, clear_token_file: bool = False
):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    try:
        flume_devices = await hass.async_add_executor_job(
            _validate_input, hass, data, clear_token_file
        )
    except RequestException as err:
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.exception("Auth exception")
        raise InvalidAuth from err
    if not flume_devices or not flume_devices.device_list:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": data[CONF_USERNAME]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for flume."""

    VERSION = 1

    def __init__(self):
        """Init flume config flow."""
        self._reauth_unique_id = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_PASSWORD] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth."""
        self._reauth_unique_id = self.context["unique_id"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauth input."""
        errors = {}
        existing_entry = await self.async_set_unique_id(self._reauth_unique_id)
        if user_input is not None:
            new_data = {**existing_entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            try:
                await validate_input(self.hass, new_data, clear_token_file=True)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_PASSWORD] = "invalid_auth"
            else:
                self.hass.config_entries.async_update_entry(
                    existing_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: existing_entry.data[CONF_USERNAME]
            },
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
