"""Config flow for the Total Connect component."""
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from total_connect_client import TotalConnectClient

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class TotalConnectConfigFlow(config_entries.ConfigFlow):
    """Total Connect config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            # Validate user input
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            valid = await self.is_valid(username, password)
    
            if valid:
                # authentication success / valid
                return self.async_create_entry(
                    title="Total Connect",
                    data={"Username": username, "Password": password},
                )
            # authentication failed / invalid
            errors["base"] = "login"

        data_schema=vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def is_valid(self, username="", password=""):
        """Return true if the given username and password are valid."""
        client = TotalConnectClient.TotalConnectClient(username, password)
        return client.token is not False
