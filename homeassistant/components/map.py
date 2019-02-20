"""
Provides a map panel for showing device locations.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/map/
"""
DOMAIN = 'map'


async def async_setup(hass, config):
    """Register the built-in map panel."""
    await hass.components.frontend.async_register_built_in_panel(
        'map', 'map', 'hass:account-location')
    return True
