"""The aurora component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AuroraDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type AuroraConfigEntry = ConfigEntry[AuroraDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AuroraConfigEntry) -> bool:
    """Set up Aurora from a config entry."""
    coordinator = AuroraDataUpdateCoordinator(hass=hass)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AuroraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
