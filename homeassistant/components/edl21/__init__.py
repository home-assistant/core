"""The edl21 component."""

from homeassistant import config_entries, core
from homeassistant.const import Platform
from .sensor import DOMAIN


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR)
    )
    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    edl = hass.data[DOMAIN]

    # Disconnect
    await edl.disconnect()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, Platform.SENSOR)
    if unload_ok:
        hass.data.pop(DOMAIN)

    return unload_ok
