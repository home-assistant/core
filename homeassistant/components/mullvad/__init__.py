"""The Mullvad VPN integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MullvadConfigEntry, MullvadCoordinator

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MullvadConfigEntry) -> None:
    """Set up Mullvad VPN integration."""
    coordinator = MullvadCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: MullvadConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
