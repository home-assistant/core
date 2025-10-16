"""The Tilt Pi integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TiltPiConfigEntry, TiltPiDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: TiltPiConfigEntry) -> bool:
    """Set up Tilt Pi from a config entry."""
    coordinator = TiltPiDataUpdateCoordinator(
        hass,
        entry,
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TiltPiConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
