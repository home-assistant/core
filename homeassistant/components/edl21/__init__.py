"""The edl21 component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Set up EDL21 integration from a config entry."""
    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, Platform.SENSOR)
    )

    return True
