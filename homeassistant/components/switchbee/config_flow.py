"""Config flow for SwitchBee Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

import switchbee
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_EXPOSE_GROUP_SWITCHES, CONF_EXPOSE_SCENARIOS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

STEP_ADVANCED_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCAN_INTERVAL, default=5): cv.positive_int,
        vol.Required(CONF_EXPOSE_SCENARIOS, default=False): cv.boolean,
        vol.Required(CONF_EXPOSE_GROUP_SWITCHES, default=False): cv.boolean,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]):
    """Validate the user input allows us to connect."""

    websession = async_get_clientsession(hass, verify_ssl=False)
    api = switchbee.SwitchBeeAPI(
        data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD], websession
    )
    try:
        await api.login()
    except switchbee.SwitchBeeError as exp:
        _LOGGER.error(exp)
        if "LOGIN_FAILED" in str(exp):
            raise InvalidAuth from switchbee.SwitchBeeError

        raise CannotConnect from switchbee.SwitchBeeError

    try:
        resp = await api.get_configuration()
        return resp[switchbee.ATTR_DATA][switchbee.ATTR_MAC]
    except switchbee.SwitchBeeError as exp:
        _LOGGER.error(exp)
        raise CannotConnect from switchbee.SwitchBeeError


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBee Smart Home."""

    VERSION = 1

    def __init__(self):
        """Device settings."""
        self._user = None
        self._pass = None
        self._cu_ip = None

    def _show_setup_form(self, user_input=None, errors=None, step_id="user"):
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        if step_id == "user":
            schema = STEP_USER_DATA_SCHEMA
        else:
            schema = STEP_ADVANCED_DATA_SCHEMA

        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    async def async_step_user(self, user_input=None):
        """Show the setup form to the user."""
        errors = {}

        if user_input is None:
            return self._show_setup_form(user_input, errors, "user")

        try:
            mac = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self._user = user_input[CONF_USERNAME]
            self._pass = user_input[CONF_PASSWORD]
            self._cu_ip = user_input[CONF_HOST]
            await self.async_set_unique_id(mac)
            self._abort_if_unique_id_configured()
            return await self.async_step_advanced()

    async def async_step_advanced(self, user_input=None, errors=None):
        """Show the advanced setup form to the user."""
        if errors is None:
            errors = {}

        if user_input is None:
            return self._show_setup_form(None, None, step_id="advanced")

        data = {
            CONF_HOST: self._cu_ip,
            CONF_USERNAME: self._user,
            CONF_PASSWORD: self._pass,
            CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
            CONF_EXPOSE_GROUP_SWITCHES: user_input[CONF_EXPOSE_GROUP_SWITCHES],
            CONF_EXPOSE_SCENARIOS: user_input[CONF_EXPOSE_SCENARIOS],
        }

        return self.async_create_entry(title=self._cu_ip, data=data)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
