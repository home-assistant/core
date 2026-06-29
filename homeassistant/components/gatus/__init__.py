"""The Gatus integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant

from .coordinator import GatusDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]

type GatusConfigEntry = ConfigEntry[GatusDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: GatusConfigEntry) -> bool:
    """Set up Gatus from a config entry."""
    coordinator = GatusDataUpdateCoordinator(hass, entry, entry.data[CONF_URL])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GatusConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
