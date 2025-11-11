"""The PTDevices integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_TOKEN, CONF_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant

from .coordinator import PTDevicesConfigEntry, PTDevicesCoordinator

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: PTDevicesConfigEntry
) -> bool:
    """Set up PTDevices from a config entry."""
    deviceId: str = config_entry.data[CONF_DEVICE_ID]
    authToken: str = config_entry.data[CONF_API_TOKEN]

    config_entry.runtime_data = coordinator = PTDevicesCoordinator(
        hass,
        config_entry,
        deviceId,
        authToken,
    )
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PTDevicesConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
