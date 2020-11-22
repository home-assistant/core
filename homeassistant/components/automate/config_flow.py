"""Config flow for Automate Pulse Hub v2 integration."""
import logging

import aiopulse2
import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required("host"): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Automate Pulse Hub v2."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step once we have info from the user."""
        errors = {}
        if user_input is not None:
            try:
                hub = aiopulse2.Hub(user_input["host"])
                await hub.test()
                info = {"title": hub.name}

                return self.async_create_entry(title=info["title"], data=user_input)
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
