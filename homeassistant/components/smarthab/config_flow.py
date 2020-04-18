"""SmartHab configuration flow."""
import logging

import pysmarthab
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SmartHabConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """SmartHab config flow."""

    def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL, default=user_input.get(CONF_EMAIL, "")
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return self._show_setup_form(user_input, None)

        username = user_input[CONF_EMAIL]
        password = user_input[CONF_PASSWORD]

        # Check if already configured
        if self.unique_id is None:
            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

        # Setup connection with SmartHab API
        hub = pysmarthab.SmartHab()

        try:
            await self.hass.async_add_executor_job(hub.login, username, password)
        except pysmarthab.RequestFailedException as ex:
            _LOGGER.error("Error while trying to reach SmartHab API.")
            _LOGGER.debug(ex, exc_info=True)
            errors["base"] = "service"
            return self._show_setup_form(user_input, errors)

        # Verify that passed in configuration works
        if not hub.is_logged_in():
            _LOGGER.error("Could not authenticate with SmartHab API")
            errors["base"] = "wrong_login"
            return self._show_setup_form(user_input, errors)

        return self.async_create_entry(
            title=username, data={CONF_EMAIL: username, CONF_PASSWORD: password},
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        return await self.async_step_user(user_input)
