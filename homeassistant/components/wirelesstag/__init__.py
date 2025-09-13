"""The Wireless Sensor Tag integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .api import WirelessTagAPI
from .coordinator import WirelessTagDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

type WirelessTagConfigEntry = ConfigEntry[WirelessTagDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WirelessTagConfigEntry) -> bool:
    """Set up Wireless Sensor Tag from a config entry."""
    api = WirelessTagAPI(
        hass,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    # Test authentication
    if not await api.async_authenticate():
        return False

    coordinator = WirelessTagDataUpdateCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WirelessTagConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
