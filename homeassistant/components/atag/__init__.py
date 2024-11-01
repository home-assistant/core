"""The ATAG Integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AtagConfigEntry, AtagDataUpdateCoordinator

DOMAIN = "atag"
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]


async def async_setup_entry(hass: HomeAssistant, entry: AtagConfigEntry) -> bool:
    """Set up Atag integration from a config entry."""

    coordinator = AtagDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=coordinator.atag.id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AtagConfigEntry) -> bool:
    """Unload Atag config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
