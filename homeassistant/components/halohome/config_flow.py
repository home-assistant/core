"""Create a config flow for the HALO Home integration."""
import logging

import halohome
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default="https://api.avi-on.com"): cv.string,
    }
)


async def _valid_input(user_input: dict) -> bool:
    try:
        await halohome.connect(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD], user_input[CONF_HOST]
        )
        return True
    except halohome.HaloHomeError:
        _LOGGER.info("halohome: Failed to login to HALO Home")
        return False


class HaloHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """The HALO Home configuration flow."""

    async def async_step_user(self, user_input: dict = None):
        """Handle the user configuration flow."""
        errors = None

        if user_input is not None and await _valid_input(user_input):
            username = user_input[CONF_USERNAME]
            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=username, data=user_input)
        elif user_input is not None:
            errors = {"base": "cannot_connect"}

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
