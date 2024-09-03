"""Config flow for sky_remote."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import selector

from .const import CONF_LEGACY_CONTROL_PORT, DOMAIN

DATA_SCHEMA = {
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_LEGACY_CONTROL_PORT, default=False): selector({"boolean": None}),
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
            logging.warning(user_input)
            return self.async_create_entry(
                title=user_input["name"],
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=vol.Schema(DATA_SCHEMA))
