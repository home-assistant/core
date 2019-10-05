"""Config flow for the Abode Security System component."""
import logging

import voluptuous as vol

from abodepy.exceptions import AbodeAuthenticationException
from homeassistant import config_entries

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class AbodeFlowHandler(config_entries.ConfigFlow):
    """Config flow for Abode."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.data_schema = {}
        self.data_schema[vol.Required(CONF_USERNAME)] = str
        self.data_schema[vol.Required(CONF_PASSWORD)] = str

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        from abodepy import Abode

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not user_input:
            return await self._show_form()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        try:
            self.hass.async_add_executor_job(Abode, username, password, True)

        # Need to add error checking if Abode server is down/not responding
        except AbodeAuthenticationException:
            return await self._show_form({"base": "invalid_credentials"})

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={CONF_USERNAME: username, CONF_PASSWORD: password},
        )

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self.hass.data.get(DOMAIN):
            _LOGGER.warning("Only one configuration of abode is allowed.")
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user(import_config)
