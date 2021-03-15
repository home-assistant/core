"""Config flow for Flexpool integration."""
import logging
import re

import voluptuous as vol

from homeassistant import config_entries, core, exceptions

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

STEP_MINER_DATA_SCHEMA = vol.Schema({"address": str, "pool": bool, "workers": bool})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    address = data["address"]
    if not re.findall("^0x[a-fA-F0-9]{40}$", address):
        return InvalidAddress

    return {"title": "Name of the device"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flexpool."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_miner(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="address", data_schema=STEP_MINER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except InvalidAddress:
            errors["base"] = "invalid_address"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="address", data_schema=STEP_MINER_DATA_SCHEMA, errors=errors
        )


class InvalidAddress(exceptions.HomeAssistantError):
    """Error to indicate the address is wrong."""
