"""The INKBIRD Bluetooth integration."""

from __future__ import annotations

from inkbird_ble import INKBIRDBluetoothDeviceData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_TYPE, DOMAIN
from .coordinator import INKBIRDActiveBluetoothProcessorCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up INKBIRD BLE device from a config entry."""
    device_type: str | None = entry.data.get(CONF_DEVICE_TYPE)
    data = INKBIRDBluetoothDeviceData(device_type)
    coordinator = INKBIRDActiveBluetoothProcessorCoordinator(hass, entry, data)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
