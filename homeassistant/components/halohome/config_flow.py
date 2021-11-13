"""Create a config flow for the HALO Home integration."""
import logging
from typing import List, Optional

import halohome
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_LOCATIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default="https://api.avi-on.com"): cv.string,
    }
)


async def _list_location_devices(user_input: dict) -> Optional[List[dict]]:
    try:
        return await halohome.list_devices(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD], user_input[CONF_HOST]
        )
    except halohome.HaloHomeError:
        _LOGGER.info("halohome: Failed to login to HALO Home")
        return None


class HaloHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """The HALO Home configuration flow."""

    async def async_step_user(self, user_input: dict = None) -> FlowResult:
        """Handle the user configuration flow."""
        errors = None

        if user_input is not None:
            if (locations := await _list_location_devices(user_input)) is not None:
                username = user_input[CONF_USERNAME]
                await self.async_set_unique_id(username)
                self._abort_if_unique_id_configured()

                title = f"HALO Home ({username})"
                data = {**user_input, CONF_LOCATIONS: locations}
                return self.async_create_entry(title=title, data=data)
            else:
                errors = {"base": "cannot_connect"}

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
