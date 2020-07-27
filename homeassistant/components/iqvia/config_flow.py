"""Config flow to configure the IQVIA component."""

from collections import OrderedDict

from pyiqvia import Client
from pyiqvia.errors import InvalidZipError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import CONF_ZIP_CODE, DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured IQVIA instances."""
    return {
        entry.data[CONF_ZIP_CODE] for entry in hass.config_entries.async_entries(DOMAIN)
    }


@config_entries.HANDLERS.register(DOMAIN)
class IQVIAFlowHandler(config_entries.ConfigFlow):
    """Handle an IQVIA config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_ZIP_CODE)] = str

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        if user_input[CONF_ZIP_CODE] in configured_instances(self.hass):
            return await self._show_form({CONF_ZIP_CODE: "identifier_exists"})

        websession = aiohttp_client.async_get_clientsession(self.hass)

        try:
            Client(user_input[CONF_ZIP_CODE], websession)
        except InvalidZipError:
            return await self._show_form({CONF_ZIP_CODE: "invalid_zip_code"})

        return self.async_create_entry(title=user_input[CONF_ZIP_CODE], data=user_input)
