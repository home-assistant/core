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
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import DOMAIN  # pylint: disable=unused-import

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Inclusive(CONF_LATITUDE, "coords"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "coords"): cv.longitude,
        vol.Optional(CONF_ELEVATION): vol.Coerce(float),
    }
)


class OpenUvFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an OpenUV config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        if user_input.get(CONF_LATITUDE):
            identifier = f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}"
        else:
            identifier = "Default Coordinates"

        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        websession = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(user_input[CONF_API_KEY], 0, 0, websession)

        try:
            await client.uv_index()
        except OpenUvError:
            return await self._show_form({CONF_API_KEY: "invalid_api_key"})

        return self.async_create_entry(title=identifier, data=user_input)
