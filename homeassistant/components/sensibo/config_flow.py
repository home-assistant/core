"""Adds config flow for Sensibo."""
from pysensibo import SensiboClient, SensiboError

from homeassistant import config_entries
from homeassistant.components.sensibo import DATA_SCHEMA, SENSIBO_API_TIMEOUT
from homeassistant.const import CONF_API_KEY, CONF_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN  # pylint:disable=unused-import


class SensiboConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for the Sensibo integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle flow initiated by user."""
        errors = {}

        if user_input is not None:
            try:
                sensibo_client = SensiboClient(
                    user_input[CONF_API_KEY],
                    session=async_get_clientsession(self.hass),
                    timeout=SENSIBO_API_TIMEOUT,
                )
                await sensibo_client.async_get_devices("room{name}")
            except SensiboError:
                errors["base"] = "connection_error"
            else:
                await self.async_set_unique_id(CONF_API_KEY)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Sensibo AC",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_ID: user_input[CONF_ID],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
