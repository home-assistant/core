"""Config flow for Rademacher HomePilot integration."""

import logging

import aiohttp
from pyhomepilot import HomePilotAPI
from pyhomepilot.auth import (  # pylint:disable=redefined-builtin
    Auth,
    AuthError,
    ConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import CONN_CLASS_LOCAL_POLL, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): str, vol.Optional(CONF_PASSWORD): str}
)


async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect."""
    async with aiohttp.ClientSession() as session:
        auth = Auth(session, data[CONF_HOST], data.get(CONF_PASSWORD))
        api = HomePilotAPI(auth)

        try:
            if data.get(CONF_PASSWORD) is not None:
                await auth.async_login()

            name = await api.async_get_system_name()
        except ConnectionError as err:
            raise CannotConnect from err
        except AuthError as err:
            raise InvalidAuth from err
        else:
            return {"title": name}


class HomepilotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rademacher HomePilot."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
