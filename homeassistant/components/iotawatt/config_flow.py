"""Config flow for iotawatt integration."""
import json
import logging

import httpx
from iotawattpy.iotawatt import Iotawatt
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import httpx_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""
    iotawatt = Iotawatt(
        "",
        data["host"],
        httpx_client.get_async_client(hass),
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
    )
    try:
        is_connected = await iotawatt.connect()
    except (KeyError, json.JSONDecodeError, httpx.HTTPError):
        return {"base": "cannot_connect"}
    except Exception:
        _LOGGER.exception("Unexpected exception")
        return {"base": "unknown"}

    if not is_connected:
        return {"base": "invalid_auth"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iotawatt."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._data = {}
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            user_input = {}

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
            }
        )
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=schema)

        if not (errors := await validate_input(self.hass, user_input)):
            return self.async_create_entry(title=user_input["host"], data=user_input)

        if errors == {"base": "invalid_auth"}:
            self._data.update(user_input)
            return await self.async_step_auth()

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_auth(self, user_input=None):
        """Authenticate user if authentication is enabled on the IoTaWatt device."""
        if user_input is None:
            user_input = {}

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                ): str,
                vol.Required(
                    CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                ): str,
            }
        )
        if not user_input:
            return self.async_show_form(step_id="auth", data_schema=data_schema)

        data = {**self._data, **user_input}

        if errors := await validate_input(self.hass, data):
            return self.async_show_form(
                step_id="auth", data_schema=data_schema, errors=errors
            )

        return self.async_create_entry(title=data["host"], data=data)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
