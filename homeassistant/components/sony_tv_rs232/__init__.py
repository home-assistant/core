"""The Sony TV RS-232 integration."""

from sony_tv_rs232 import SonyTV

from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .coordinator import SonyTVCoordinator, SonyTVRS232ConfigEntry

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: SonyTVRS232ConfigEntry) -> None:
    """Set up a Sony TV from a config entry."""
    tv = SonyTV(entry.data[CONF_PORT])
    coordinator = SonyTVCoordinator(hass, entry, tv)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: SonyTVRS232ConfigEntry
) -> None:
    """Unload a config entry (the coordinator closes the serial port on unload)."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
