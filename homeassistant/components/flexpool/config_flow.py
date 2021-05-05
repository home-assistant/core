"""Config flow for Flexpool integration."""
import logging
import re

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDRESS): str,
        vol.Optional("workers"): bool,
    }
)


async def validate_input(hass: core.HomeAssistant, data: dict):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    address = data["address"]
    if not re.findall("^0x[a-fA-F0-9]{40}$", address):
        raise InvalidAddress

    return {"title": address}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flexpool."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAddress:
                errors["base"] = "invalid_address"
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", error)
                errors["base"] = "unknown"
            if not errors:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidAddress(exceptions.HomeAssistantError):
    """Error to indicate the address is wrong."""
