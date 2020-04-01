"""Config flow to configure the WWLLN integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.helpers import config_validation as cv

from .const import (  # pylint: disable=unused-import
    CONF_WINDOW,
    DEFAULT_RADIUS,
    DEFAULT_WINDOW,
    DOMAIN,
)


class WWLLNFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a WWLLN config flow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def data_schema(self):
        """Return the data schema for the user form."""
        return vol.Schema(
            {
                vol.Optional(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Optional(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): cv.positive_int,
            }
        )

    async def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=self.data_schema, errors=errors or {}
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return await self._show_form()

        latitude = user_input.get(CONF_LATITUDE, self.hass.config.latitude)
        longitude = user_input.get(CONF_LONGITUDE, self.hass.config.longitude)

        identifier = f"{latitude}, {longitude}"

        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=identifier,
            data={
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_RADIUS: user_input.get(CONF_RADIUS, DEFAULT_RADIUS),
                CONF_WINDOW: user_input.get(
                    CONF_WINDOW, DEFAULT_WINDOW.total_seconds()
                ),
            },
        )
