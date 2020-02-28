"""Config flow for the Atag component."""
from aiohttp import ClientSession
from pyatag import DEFAULT_PORT, AtagDataStore, AtagException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE, CONF_EMAIL, CONF_HOST, CONF_PORT
from homeassistant.core import callback

from . import DOMAIN  # pylint: disable=unused-import

DATA_SCHEMA = {
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_EMAIL): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
}


class AtagConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Atag."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if not user_input:
            return await self._show_form()

        try:
            async with ClientSession() as session:
                atag = AtagDataStore(session, **user_input)
                await atag.async_check_pair_status()

        except AtagException:
            return await self._show_form({"base": "connection_error"})

        user_input.update({CONF_DEVICE: atag.device})
        return self.async_create_entry(title=atag.device, data=user_input)

    @callback
    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(DATA_SCHEMA),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return await self.async_step_user(import_config)
