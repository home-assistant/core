"""Config flow for the Total Connect component."""
from total_connect_client import TotalConnectClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN  # pylint: disable=unused-import


class TotalConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Total Connect config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            # Validate user input
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            valid = await self.is_valid(username, password)

            if valid:
                # authentication success / valid
                return self.async_create_entry(
                    title="Total Connect",
                    data={CONF_USERNAME: username, CONF_PASSWORD: password},
                )
            # authentication failed / invalid
            errors["base"] = "invalid_auth"

        data_schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    async def is_valid(self, username="", password=""):
        """Return true if the given username and password are valid."""
        client = await self.hass.async_add_executor_job(
            TotalConnectClient.TotalConnectClient, username, password
        )
        return client.is_valid_credentials()
