"""Config flow for the Atag component."""
import pyatag  # from pyatag import DEFAULT_PORT, AtagException, AtagOne
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN  # pylint: disable=unused-import

DATA_SCHEMA = {
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_EMAIL): str,
    vol.Required(CONF_PORT, default=pyatag.const.DEFAULT_PORT): vol.Coerce(int),
}


class AtagConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Atag."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""

        if not user_input:
            return await self._show_form()
        session = async_get_clientsession(self.hass)
        try:
            atag = pyatag.AtagOne(session=session, **user_input)
            await atag.authorize()
            await atag.update(force=True)

        except pyatag.errors.Unauthorized:
            return await self._show_form({"base": "unauthorized"})
        except pyatag.errors.AtagException:
            return await self._show_form({"base": "connection_error"})

        await self.async_set_unique_id(atag.id)
        self._abort_if_unique_id_configured(updates=user_input)

        return self.async_create_entry(title=atag.id, data=user_input)

    @callback
    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(DATA_SCHEMA),
            errors=errors if errors else {},
        )
