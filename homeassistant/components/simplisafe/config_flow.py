"""Config flow to configure the SimpliSafe component."""

from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_CODE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import aiohttp_client

from .const import DATA_SIMPLISAFE_CLIENT, DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured SimpliSafe instances."""
    return set(
        entry.data[CONF_USERNAME]
        for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class SimpliSafeFlowHandler(config_entries.ConfigFlow):
    """Handle a SimpliSafe config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        pass

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        from simplipy import API
        from simplipy.errors import SimplipyError

        errors = {}

        if user_input is not None:
            if user_input[CONF_USERNAME] in configured_instances(self.hass):
                errors['base'] = 'identifier_exists'
            else:
                websession = aiohttp_client.async_get_clientsession(self.hass)
                try:
                    self.hass.data[DOMAIN][
                        DATA_SIMPLISAFE_CLIENT] = API.login_via_credentials(
                            user_input[CONF_USERNAME],
                            user_input[CONF_PASSWORD], websession)

                    return self.async_create_entry(
                        title=user_input[CONF_USERNAME],
                        data=user_input,
                    )
                except SimplipyError:
                    errors['base'] = 'invalid_credentials'

        data_schema = OrderedDict()
        data_schema[vol.Required(CONF_USERNAME)] = str
        data_schema[vol.Required(CONF_PASSWORD)] = str
        data_schema[vol.Optional(CONF_NAME)] = str
        data_schema[vol.Optional(CONF_CODE)] = str

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )
