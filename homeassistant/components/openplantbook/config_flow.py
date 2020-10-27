"""Config flow for OpenPlantBook integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core

from . import OpenPlantBookApi
from .const import ATTR_API, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({"client_id": str, "secret": str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    try:
        hass.data[DOMAIN][ATTR_API] = OpenPlantBookApi(
            data["client_id"], data["secret"]
        )
    except Exception as ex:
        _LOGGER.debug("Unable to connect to OpenPlantbook: %s", ex)
        raise

    return {"title": "Openplantbook API"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenPlantBook."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except Exception as ex:
                _LOGGER.error("Unable to connect to OpenPlantbook: %s", ex)
                raise

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
