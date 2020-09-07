"""The 1-Wire component."""
import voluptuous as vol

from .const import DOMAIN, SUPPORTED_PLATFORMS

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({}, extra=vol.ALLOW_EXTRA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, config):
    """Old way of setting up 1-Wire integrations."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up a 1-Wire proxy for a config entry."""
    for component in SUPPORTED_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = True
    for component in SUPPORTED_PLATFORMS:
        unload_ok = unload_ok and await hass.config_entries.async_forward_entry_unload(
            config_entry, component
        )
    return unload_ok
