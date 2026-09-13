"""The OpenWrt (ubus) integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import UbusConfigEntry, UbusDataUpdateCoordinator

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> bool:
    """Set up ubus from a config entry."""
    coordinator = UbusDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: UbusConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
