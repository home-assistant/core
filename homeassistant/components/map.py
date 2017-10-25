"""
Provides a map panel for showing device locations.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/map/
"""
import asyncio
import voluptuous as vol

from homeassistant.components.frontend import register_built_in_panel
import homeassistant.helpers.config_validation as cv


DOMAIN = 'map'

CONF_TILE_PROVIDER = 'tile_provider'

DEFAULT_TILE_PROVIDER = 'CartoDB.Positron'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_TILE_PROVIDER, default=DEFAULT_TILE_PROVIDER):
            cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Register the built-in map panel."""
    yield from hass.components.frontend.async_register_built_in_panel(
        'map', 'Map', 'mdi:account-location', config={
            CONF_TILE_PROVIDER: config[DOMAIN].get(CONF_TILE_PROVIDER)
        })
    return True
