"""The WeConnect integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import WeConnectCoordinator

PLATFORMS = [Platform.SENSOR]


type WeConnectConfigEntry = ConfigEntry[WeConnectCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WeConnectConfigEntry,
) -> bool:
    """Set up the WeConnect integration."""
    coordinator = WeConnectCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeConnectConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
