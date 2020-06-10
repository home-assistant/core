"""Adds config flow for Mill integration."""
import logging

from mill import Mill
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class MillConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mill integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors={},
            )

        username = user_input[CONF_USERNAME].replace(" ", "")
        password = user_input[CONF_PASSWORD].replace(" ", "")

        mill_data_connection = Mill(
            username, password, websession=async_get_clientsession(self.hass),
        )

        errors = {}

        if not await mill_data_connection.connect():
            errors["connection_error"] = "connection_error"
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors,
            )

        unique_id = username

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=unique_id, data={CONF_USERNAME: username, CONF_PASSWORD: password},
        )
