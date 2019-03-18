"""Config flow to configure the AIS Spotify Service component."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY, CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv



@callback
def configured_instances(hass):
    """Return a set of configured AIS Spotify Service instances."""
    return set(
        '{0}, {1}'.format(
            entry.data.get(CONF_LATITUDE, hass.config.latitude),
            entry.data.get(CONF_LONGITUDE, hass.config.longitude))
        for entry in hass.config_entries.async_entries("ais_spotify_service"))


@config_entries.HANDLERS.register("ais_spotify_service")
class AisSpotifyServiceFlowHandler(config_entries.ConfigFlow):
    """Handle an AIS Spotify Service config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if user_input is not None:
            name = "jjjj"
            errors['base'] = 'name_exists'

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required(CONF_LATITUDE): cv.latitude,
                vol.Required(CONF_LONGITUDE): cv.longitude,
                vol.Optional("rad"): vol.Coerce(float),
                vol.Optional("icon"): str,
                vol.Optional("pass"): bool,
            }),
            errors=errors,
        )
