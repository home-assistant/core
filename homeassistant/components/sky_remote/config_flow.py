"""Config flow for sky_remote."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

DATA_SCHEMA = {
    vol.Required(CONF_HOST): cv.string,
}


class SkyRemoteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sky Remote."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step."""
        if user_input is not None:
            logging.debug("user_input: %s", user_input)
            return self.async_create_entry(
                title=user_input[CONF_HOST],
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=vol.Schema(DATA_SCHEMA))
