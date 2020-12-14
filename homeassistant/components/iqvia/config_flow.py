"""Config flow to configure the IQVIA component."""
from pyiqvia import Client
from pyiqvia.errors import InvalidZipError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client

from .const import CONF_ZIP_CODE, DOMAIN  # pylint:disable=unused-import


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an IQVIA config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.data_schema = vol.Schema({vol.Required(CONF_ZIP_CODE): str})

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=self.data_schema)

        await self.async_set_unique_id(user_input[CONF_ZIP_CODE])
        self._abort_if_unique_id_configured()

        websession = aiohttp_client.async_get_clientsession(self.hass)

        try:
            Client(user_input[CONF_ZIP_CODE], websession)
        except InvalidZipError:
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
                errors={CONF_ZIP_CODE: "invalid_zip_code"},
            )

        return self.async_create_entry(title=user_input[CONF_ZIP_CODE], data=user_input)
