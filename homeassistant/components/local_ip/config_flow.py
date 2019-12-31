"""Config flow for local_ip."""
import logging

import voluptuous as vol

from homeassistant import config_entries

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SimpleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for local_ip."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional("name", default=DOMAIN): str}),
            errors={},
        )
