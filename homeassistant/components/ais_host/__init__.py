"""Support for the definition of AIS hostname."""

from .config_flow import configured_host

DOMAIN = "ais_host"


async def async_setup(hass, config):
    """Set up if necessary."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up ais host as config entry."""
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    return True
