"""Config flow for flume integration."""
from functools import partial
import logging

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


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    client_id = data[CONF_CLIENT_ID]
    client_secret = data[CONF_CLIENT_SECRET]
    flume_token_full_path = hass.config.path(f"{BASE_TOKEN_FILENAME}-{username}")

    try:
        flume_auth = await hass.async_add_executor_job(
            partial(
                FlumeAuth,
                username,
                password,
                client_id,
                client_secret,
                flume_token_file=flume_token_full_path,
            )
        )
        flume_devices = await hass.async_add_executor_job(FlumeDeviceList, flume_auth)
    except RequestException as err:
        raise CannotConnect from err
    except Exception as err:
        raise InvalidAuth from err
    if not flume_devices or not flume_devices.device_list:
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": username}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for flume."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
