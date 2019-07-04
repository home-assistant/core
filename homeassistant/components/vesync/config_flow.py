"""Config flow utilities."""
import logging
from collections import OrderedDict
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (CONF_TIME_ZONE, CONF_USERNAME, CONF_PASSWORD)


DOMAIN = 'vesync'

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return already configured instances."""
    return set(
        entry.data[CONF_USERNAME]
        for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class VeSyncFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Instantiate config flow."""
        self._username = None
        self._password = None
        self._time_zone = None
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_USERNAME)] = str
        self.data_schema[vol.Required(CONF_PASSWORD)] = str
        self.data_schema[vol.Optional(CONF_TIME_ZONE)] = str

    async def _show_form(self, errors=None):
        """Show form to the user."""
        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Handle external yaml configuration."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if not user_input:
            return await self._show_form()

        if user_input[CONF_USERNAME] in configured_instances(self.hass):
            return await self._show_form({CONF_USERNAME: 'Username Exists'})

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        self._time_zone = user_input.get(CONF_TIME_ZONE, None)

        return self.async_create_entry(
            title=self._username,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_TIME_ZONE: self._time_zone,
            },
        )
