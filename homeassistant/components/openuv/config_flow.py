"""Config flow to configure the OpenUV component."""
from pyopenuv import Client
from pyopenuv.errors import OpenUvError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import DOMAIN


@callback
def configured_instances(hass):
    """Return a set of configured OpenUV instances."""
    return {
        f"{entry.data.get(CONF_LATITUDE, hass.config.latitude)}, "
        f"{entry.data.get(CONF_LONGITUDE, hass.config.longitude)}"
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


@config_entries.HANDLERS.register(DOMAIN)
class OpenUvFlowHandler(config_entries.ConfigFlow):
    """Handle an OpenUV config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_LATITUDE): cv.latitude,
                vol.Optional(CONF_LONGITUDE): cv.longitude,
                vol.Optional(CONF_ELEVATION): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors if errors else {}
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""

        if not user_input:
            return await self._show_form()

        identifier = (
            f"{user_input.get(CONF_LATITUDE, self.hass.config.latitude)}, "
            f"{user_input.get(CONF_LONGITUDE, self.hass.config.longitude)}"
        )
        if identifier in configured_instances(self.hass):
            return await self._show_form({CONF_LATITUDE: "identifier_exists"})

        websession = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(user_input[CONF_API_KEY], 0, 0, websession)

        try:
            await client.uv_index()
        except OpenUvError:
            return await self._show_form({CONF_API_KEY: "invalid_api_key"})

        return self.async_create_entry(title=identifier, data=user_input)
