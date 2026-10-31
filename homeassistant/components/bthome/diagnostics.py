"""Diagnostics support for the BTHome integration."""

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_BINDKEY, CONF_DISCOVERED_EVENT_CLASSES
from .types import BTHomeConfigEntry

MASKED_ADDRESS = "*" * 12


def _mask_address(data: bytes, address: str) -> str:
    """Return data as hex with the address masked, as payloads can embed the MAC."""
    octets = address.lower().split(":")
    hex_data = data.hex()
    for needle in ("".join(octets), "".join(reversed(octets))):
        hex_data = hex_data.replace(needle, MASKED_ADDRESS)
    return hex_data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BTHomeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    device_data = coordinator.device_data
    service_info = bluetooth.async_last_service_info(
        hass, coordinator.address, connectable=False
    )
    return {
        "config_entry": {
            "encryption_configured": bool(entry.data.get(CONF_BINDKEY)),
            "sleepy_device": coordinator.sleepy_device,
            "discovered_event_classes": sorted(
                entry.data.get(CONF_DISCOVERED_EVENT_CLASSES, [])
            ),
        },
        "devices": [
            {
                "manufacturer": device.manufacturer,
                "model": device.model,
            }
            for device in dr.async_entries_for_config_entry(
                dr.async_get(hass), entry.entry_id
            )
        ],
        "device_data": {
            "bthome_version": device_data.bthome_version.value,
            "encryption_scheme": device_data.encryption_scheme.value,
            "bindkey_verified": device_data.bindkey_verified,
            "decryption_failed": device_data.decryption_failed,
            "downgrade_detected": device_data.downgrade_detected,
            "sleepy_device": device_data.sleepy_device,
            "device_type_id": device_data.device_type_id,
            "packet_id": device_data.packet_id,
            "encryption_counter": device_data.encryption_counter,
            "unhandled": device_data.unhandled,
        },
        "last_advertisement": service_info
        and {
            "rssi": service_info.rssi,
            "tx_power": service_info.tx_power,
            "connectable": service_info.connectable,
            "service_uuids": service_info.service_uuids,
            "service_data": {
                uuid: _mask_address(data, coordinator.address)
                for uuid, data in service_info.service_data.items()
            },
            "manufacturer_data": {
                str(company_id): _mask_address(data, coordinator.address)
                for company_id, data in service_info.manufacturer_data.items()
            },
        },
    }
