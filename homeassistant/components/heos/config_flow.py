"""Config flow to configure Heos."""
import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import DOMAIN


def format_title(host: str) -> str:
    """Format the title for config entries."""
    return "Controller ({})".format(host)


@config_entries.HANDLERS.register(DOMAIN)
class HeosFlowHandler(config_entries.ConfigFlow):
    """Define a flow for HEOS."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_discovery(self, discovery_info):
        """Handle a discovered Heos device."""
        return await self.async_step_user(
            {CONF_HOST: discovery_info[CONF_HOST]})

    async def async_step_import(self, user_input=None):
        """Occurs when an entry is setup through config."""
        host = user_input[CONF_HOST]
        return self.async_create_entry(
            title=format_title(host),
            data={CONF_HOST: host})

    async def async_step_user(self, user_input=None):
        """Obtain host and validate connection."""
        from pyheos import Heos

        # Only a single entry is needed for all devices
        entries = self.hass.config_entries.async_entries(DOMAIN)
        if entries:
            return self.async_abort(reason='already_setup')

        # Try connecting to host if provided
        errors = {}
        host = None
        if user_input is not None:
            host = user_input[CONF_HOST]
            heos = Heos(host)
            try:
                await heos.connect()
                return await self.async_step_import(user_input)
            except (asyncio.TimeoutError, ConnectionError):
                errors[CONF_HOST] = 'connection_failure'
            finally:
                await heos.disconnect()

        # Return form
        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=host): str
            }),
            errors=errors)
