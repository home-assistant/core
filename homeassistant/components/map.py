"""
Provides a map panel for showing device locations.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/map/
"""
import asyncio

DOMAIN = 'map'


@asyncio.coroutine
def async_setup(hass, config):
    """Register the built-in map panel."""
    yield from hass.components.frontend.async_register_built_in_panel(
        'map', 'map', 'mdi:account-location')
    return True
