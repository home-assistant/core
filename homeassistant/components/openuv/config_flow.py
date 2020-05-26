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

from .const import DOMAIN


class OpenUvFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an OpenUV config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def data_schema(self):
        """Return the data schema."""
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(
                    CONF_ELEVATION, default=self.hass.config.elevation
                ): vol.Coerce(float),
            }
        )

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.data_schema,
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        identifier = f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}"

        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        websession = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(user_input[CONF_API_KEY], 0, 0, websession)

        try:
            await client.uv_index()
        except OpenUvError:
            return await self._show_form({CONF_API_KEY: "invalid_api_key"})

        return self.async_create_entry(title=identifier, data=user_input)
