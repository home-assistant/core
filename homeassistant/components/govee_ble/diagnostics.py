"""Diagnostics support for the Govee Bluetooth integration."""

from typing import Any

from govee_ble import DeviceKey, GoveeBluetoothDeviceData

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_TYPE
from .coordinator import GoveeBLEConfigEntry


def _format_key(device_key: DeviceKey) -> str:
    """Format a device key, including the sub-device id when present."""
    if device_key.device_id is None:
        return device_key.key
    return f"{device_key.key} ({device_key.device_id})"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GoveeBLEConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    model_info = coordinator.model_info
    diagnostics: dict[str, Any] = {
        "device_type": entry.data.get(CONF_DEVICE_TYPE),
        "model_info": {
            "model_id": model_info.model_id,
            "sensor_type": model_info.sensor_type.value,
            "button_count": model_info.button_count,
            "sleepy": model_info.sleepy,
            "requires_active_scan": model_info.requires_active_scan,
        }
        if model_info
        else None,
        "coordinator": {
            "available": coordinator.available,
            "last_update_success": coordinator.last_update_success,
            "scanning_mode": coordinator.mode.name,
        },
        "service_info": None,
        "parsed_advertisement": None,
    }
    address = entry.unique_id
    assert address is not None
    if not (
        service_info := bluetooth.async_last_service_info(
            hass, address, connectable=False
        )
    ):
        return diagnostics

    diagnostics["service_info"] = {
        "rssi": service_info.rssi,
        "connectable": service_info.connectable,
        "manufacturer_data": {
            manufacturer_id: data.hex()
            for manufacturer_id, data in service_info.manufacturer_data.items()
        },
        "service_data": {
            uuid: data.hex() for uuid, data in service_info.service_data.items()
        },
        "service_uuids": service_info.service_uuids,
    }
    # Device names embed part of the MAC, so only model info is exposed
    update = GoveeBluetoothDeviceData().update(service_info)
    diagnostics["parsed_advertisement"] = {
        "devices": [
            {
                "device_id": device_id,
                "model": device.model,
                "manufacturer": device.manufacturer,
                "sw_version": device.sw_version,
                "hw_version": device.hw_version,
            }
            for device_id, device in update.devices.items()
        ],
        "sensors": {
            _format_key(key): value.native_value
            for key, value in update.entity_values.items()
        },
        "binary_sensors": {
            _format_key(key): value.native_value
            for key, value in update.binary_entity_values.items()
        },
        "events": {
            _format_key(key): event.event_type for key, event in update.events.items()
        },
    }
    return diagnostics
