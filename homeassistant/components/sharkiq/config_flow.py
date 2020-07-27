"""Config flow for Shark IQ integration."""

import asyncio
import logging

import aiohttp
import async_timeout
from sharkiqpy import SharkIqAuthError, get_ayla_api
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN  # pylint:disable=unused-import

SHARKIQ_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    ayla_api = get_ayla_api(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        websession=hass.helpers.aiohttp_client.async_get_clientsession(hass),
    )

    try:
        with async_timeout.timeout(10):
            _LOGGER.debug("Initialize connection to Ayla networks API")
            await ayla_api.async_sign_in()
    except (asyncio.TimeoutError, aiohttp.ClientError):
        raise CannotConnect
    except SharkIqAuthError:
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": f"Shark IQ ({data[CONF_USERNAME]:s})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shark IQ."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # noinspection PyBroadException
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=SHARKIQ_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
