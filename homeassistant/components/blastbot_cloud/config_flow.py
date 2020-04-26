"""Blastbot Cloud config flow."""

from aiohttp import ClientError
from blastbot_cloud_api.api import BlastbotCloudAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import DOMAIN, LOGGER


class BlastbotCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Blastbot Cloud config flow."""

    def __init__(self):
        """Initialize."""
        self.data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        if not user_input:
            return self._show_form()

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        try:
            api = BlastbotCloudAPI()
            successful_login = await api.async_login(username, password)
            if not successful_login:
                await api.async_close()
                return self._show_form({"base": "invalid_credentials"})
        except ClientError as ex:
            LOGGER.error("Unable to connect to Blastbot Cloud: %s", str(ex))
            await api.async_close()
            return self._show_form({"base": "connection_error"})

        await api.async_close()

        unique_id = f"{DOMAIN}_{username.lower()}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={CONF_USERNAME: username, CONF_PASSWORD: password},
        )

    @callback
    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )
