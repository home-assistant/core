"""The OMIE - Spain and Portugal electricity prices integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import OMIEConfigEntry, OMIECoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OMIEConfigEntry) -> bool:
    """Set up from a config entry."""
    entry.runtime_data = OMIECoordinator(hass, entry)

    await entry.runtime_data.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OMIEConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
