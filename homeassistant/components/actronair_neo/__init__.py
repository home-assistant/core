"""The Actron Air Neo integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .const import PLATFORM
from .coordinator import ActronNeoDataUpdateCoordinator

type ActronConfigEntry = ConfigEntry[ActronNeoDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ActronConfigEntry) -> bool:
    """Set up Actron Air Neo integration from a config entry."""

    # Initialize the data coordinator
    pairing_token = entry.data[CONF_API_TOKEN]
    coordinator = ActronNeoDataUpdateCoordinator(hass, pairing_token)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ActronConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORM)
