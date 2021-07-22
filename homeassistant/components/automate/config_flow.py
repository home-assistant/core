"""Config flow for Automate Pulse Hub v2 integration."""
import logging

import aiopulse2
import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required("host"): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Automate Pulse Hub v2."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step once we have info from the user."""
        if user_input is not None:
            try:
                hub = aiopulse2.Hub(user_input["host"])
                await hub.test()
                title = hub.name
            except Exception:  # pylint: disable=broad-except
                return self.async_show_form(
                    step_id="user",
                    data_schema=DATA_SCHEMA,
                    errors={"base": "cannot_connect"},
                )

            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
