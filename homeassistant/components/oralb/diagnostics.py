"""Diagnostics support for the Oral-B integration."""

from typing import TYPE_CHECKING, Any

from oralb_ble import OralBBluetoothDeviceData

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from . import OralBConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OralBConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    diagnostics: dict[str, Any] = {
        "coordinator": {
            "available": coordinator.available,
            "last_update_success": coordinator.last_update_success,
            "last_poll_successful": coordinator.last_poll_successful,
        },
        "service_info": None,
        "parsed_advertisement": None,
    }
    address = entry.unique_id
    if TYPE_CHECKING:
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
    update = OralBBluetoothDeviceData().update(service_info)
    diagnostics["parsed_advertisement"] = {
        "devices": [
            {
                "model": device.model,
                "manufacturer": device.manufacturer,
                "sw_version": device.sw_version,
                "hw_version": device.hw_version,
            }
            for device in update.devices.values()
        ],
        "sensors": {
            key.key: value.native_value for key, value in update.entity_values.items()
        },
        "binary_sensors": {
            key.key: value.native_value
            for key, value in update.binary_entity_values.items()
        },
    }
    return diagnostics
