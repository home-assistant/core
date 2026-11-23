"""Diagnostics support for the Xiaomi BLE integration."""

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .types import XiaomiBLEConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: XiaomiBLEConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.device_data
    service_info = bluetooth.async_last_service_info(
        hass, coordinator.address, connectable=False
    )
    return {
        "devices": [
            {
                "manufacturer": device.manufacturer,
                "model": device.model,
                "sw_version": device.sw_version,
                "hw_version": device.hw_version,
            }
            for device in dr.async_entries_for_config_entry(
                dr.async_get(hass), entry.entry_id
            )
        ],
        "available": coordinator.available,
        "last_update_success": coordinator.last_update_success,
        "sleepy_device": coordinator.sleepy_device,
        "discovered_event_classes": sorted(coordinator.discovered_event_classes),
        "pending": data.pending,
        "encryption_scheme": data.encryption_scheme.value,
        "bindkey_configured": data.bindkey is not None,
        "bindkey_verified": data.bindkey_verified,
        "decryption_failed": data.decryption_failed,
        "unhandled": data.unhandled,
        "last_advertisement": {
            "connectable": service_info.connectable,
            "rssi": service_info.rssi,
            "service_uuids": service_info.service_uuids,
        }
        if service_info
        else None,
    }
