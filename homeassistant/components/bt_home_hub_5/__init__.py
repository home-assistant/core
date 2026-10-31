"""The BT Home Hub 5 integration."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import BTHomeHub5ConfigEntry, BTHomeHub5DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: BTHomeHub5ConfigEntry) -> None:
    """Set up BT Home Hub 5 from a config entry."""
    coordinator = BTHomeHub5DataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: BTHomeHub5ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
