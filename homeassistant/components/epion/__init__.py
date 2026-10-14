"""The Epion integration."""

from epion import Epion

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .coordinator import EpionConfigEntry, EpionCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: EpionConfigEntry) -> None:
    """Set up the Epion coordinator from a config entry."""
    api = Epion(entry.data[CONF_API_KEY])
    coordinator = EpionCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: EpionConfigEntry) -> None:
    """Unload Epion config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
