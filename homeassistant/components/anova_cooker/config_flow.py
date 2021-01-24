"""Config flow for Anova Sous Vide Cooker integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({"device_id": str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    return {"device_id": data["device_id"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Anova Sous Vide Cooker."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "cannot_connect"
        else:
            cooker_name = "Cooker {}".format(info["device_id"])
            return self.async_create_entry(title=cooker_name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
