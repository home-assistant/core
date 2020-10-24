"""The 1-Wire component."""
import asyncio

from .const import SUPPORTED_PLATFORMS


async def async_setup(hass, config):
    """Set up 1-Wire integrations."""
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
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in SUPPORTED_PLATFORMS
            ]
        )
    )
    return unload_ok
