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

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required("host"): str, vol.Optional("password"): str}
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    async with aiohttp.ClientSession() as session:
        auth = Auth(session, data["host"], data.get("password"))
        api = HomePilotAPI(auth)

        try:
            if "password" in data:
                await auth.async_login()

            name = await api.async_get_system_name()
        except ConnectionError as err:
            raise CannotConnect from err
        except AuthError as err:
            raise InvalidAuth from err
        else:
            return {"title": name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rademacher HomePilot."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

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


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
