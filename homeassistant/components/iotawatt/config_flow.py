"""Config flow for iotawatt integration."""

from __future__ import annotations

import logging

from iotawattpy.iotawatt import Iotawatt
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import httpx_client

from .const import CONNECTION_ERRORS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    iotawatt = Iotawatt(
        "",
        data[CONF_HOST],
        httpx_client.get_async_client(hass),
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
    )
    try:
        is_connected = await iotawatt.connect()
    except CONNECTION_ERRORS:
        return {"base": "cannot_connect"}
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        return {"base": "unknown"}

    if not is_connected:
        return {"base": "invalid_auth"}

    return {}


class IOTaWattConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iotawatt."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self._data = {}

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
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

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

        return self.async_create_entry(title=data[CONF_HOST], data=data)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
