"""Config flow for SwitchBee Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

import switchbee
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class Hub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, central_unit_ip: str) -> None:
        """Initialize."""
        self.central_unit_ip = central_unit_ip

    async def authenticate(self, username: str, password: str) -> dict:
        """Test if we can authenticate with the host."""
        return await switchbee.SwitchBee(
            self.central_unit_ip, username, password
        ).login()


async def validate_input(hass: HomeAssistant, data: dict[str, Any]):
    """Validate the user input allows us to connect."""

    hub = Hub(data[CONF_IP_ADDRESS])

    resp = await hub.authenticate(data[CONF_USERNAME], data[CONF_PASSWORD])
    if resp[switchbee.ATTR_STATUS] == switchbee.STATUS_LOGIN_FAILED:
        raise InvalidAuth

    if resp[switchbee.ATTR_STATUS] == switchbee.STATUS_FAILED:
        raise CannotConnect


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBee Smart Home."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Show the setup form to the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title="SwitchBee", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
