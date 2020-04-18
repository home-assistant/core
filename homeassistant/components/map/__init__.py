"""Support for showing device locations."""
DOMAIN = "map"


async def async_setup(hass, config):
    """Register the built-in map panel."""
    hass.components.frontend.async_register_built_in_panel(
        "map", "map", "hass:tooltip-account"
    )
    return True
