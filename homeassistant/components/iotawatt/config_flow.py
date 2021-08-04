"""Config flow for iotawatt integration."""
import json
import logging

import httpx
from httpx import AsyncClient
from iotawattpy.iotawatt import Iotawatt
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
    }
)


class IotawattHub:
    """IotaWatt main object."""

    def __init__(self, name):
        """Initialize."""
        self.name = name

    async def authenticate(self, username, password) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = AsyncClient()
    iotawatt = Iotawatt(data["name"], data["host"], session)
    try:
        is_connected = await iotawatt.connect()
        _LOGGER.debug("isConnected: %s", is_connected)
    except (KeyError, json.JSONDecodeError, httpx.HTTPError):
        raise CannotConnect

    if not is_connected:
        raise InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": data["name"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iotawatt."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        self._data.update(user_input)

        try:
            await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            return await self.async_step_auth()
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=self._data["name"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth(self, user_input=None):
        """Authenticate user if authentication is enabled on the IoTaWatt device."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        _LOGGER.debug("Data: %s", self._data)
        if user_input is None:
            return self.async_show_form(step_id="auth", data_schema=data_schema)
        self._data.update(user_input)
        return self.async_create_entry(title=self._data["name"], data=self._data)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
