"""Config flow for Monoprice 6-Zone Amplifier integration."""
import logging

from pymonoprice import get_async_monoprice
from serial import SerialException
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PORT

from .const import (
    CONF_SOURCE_1,
    CONF_SOURCE_2,
    CONF_SOURCE_3,
    CONF_SOURCE_4,
    CONF_SOURCE_5,
    CONF_SOURCE_6,
    CONF_SOURCES,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PORT): str,
        vol.Optional(CONF_SOURCE_1): str,
        vol.Optional(CONF_SOURCE_2): str,
        vol.Optional(CONF_SOURCE_3): str,
        vol.Optional(CONF_SOURCE_4): str,
        vol.Optional(CONF_SOURCE_5): str,
        vol.Optional(CONF_SOURCE_6): str,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    try:
        await get_async_monoprice(data[CONF_PORT], hass.loop)
    except SerialException:
        _LOGGER.error("Error connecting to Monoprice controller")
        raise CannotConnect

    sources_config = {
        1: data.get(CONF_SOURCE_1),
        2: data.get(CONF_SOURCE_2),
        3: data.get(CONF_SOURCE_3),
        4: data.get(CONF_SOURCE_4),
        5: data.get(CONF_SOURCE_5),
        6: data.get(CONF_SOURCE_6),
    }
    sources = {
        index: name.strip()
        for index, name in sources_config.items()
        if (name is not None and name.strip() != "")
    }
    # Return info that you want to store in the config entry.
    return {CONF_PORT: data[CONF_PORT], CONF_SOURCES: sources}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Monoprice 6-Zone Amplifier."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)

                return self.async_create_entry(title=user_input[CONF_PORT], data=info)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
