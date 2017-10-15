"""
Provides a map panel for showing device locations.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/map/
"""
import asyncio

from homeassistant.components.frontend import register_built_in_panel

DOMAIN = 'map'


@asyncio.coroutine
def async_setup(hass, config):
    """Register the built-in map panel."""
    register_built_in_panel(hass, 'map', 'Map', 'mdi:account-location')
    return True
