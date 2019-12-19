"""Config flow for localip."""
import logging

import voluptuous as vol

from homeassistant import config_entries

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SimpleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for localip."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        for entry in self._async_current_entries():
            _LOGGER.warning(entry)

        errors = {}
        if user_input is not None:
            try:
                return self.async_create_entry(
                    title=user_input["name"], data=user_input
                )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional("name", default=DOMAIN): str}),
            errors=errors,
        )
