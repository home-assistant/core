"""Diagnostics support for Indevolt integration."""

from typing import Any

from indevolt_api import IndevoltBattery, IndevoltSystem

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL_NUMBER
from .coordinator import IndevoltConfigEntry

# Redact sensitive information from diagnostics (host and serial numbers)
TO_REDACT = {
    CONF_HOST,
    CONF_SERIAL_NUMBER,
    IndevoltSystem.SERIAL_NUMBER,
    IndevoltBattery.MAIN_SERIAL_NUMBER,
    IndevoltBattery.PACK_1_SERIAL_NUMBER,
    IndevoltBattery.PACK_2_SERIAL_NUMBER,
    IndevoltBattery.PACK_3_SERIAL_NUMBER,
    IndevoltBattery.PACK_4_SERIAL_NUMBER,
    IndevoltBattery.PACK_5_SERIAL_NUMBER,
}


def _redact_mac(mac_address: str) -> str:
    """Redact the device-specific part of a MAC address.

    Keeps the OUI, which is used for discovery.
    """
    parts = mac_address.split(":")
    return ":".join([*parts[:3], "XX", "XX", "XX"])


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IndevoltConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    device_info = {
        "model": coordinator.device_model,
        "generation": coordinator.generation,
        "serial_number": coordinator.serial_number,
        "firmware_version": coordinator.firmware_version,
        "mac_address": _redact_mac(coordinator.mac_address)
        if coordinator.mac_address
        else None,
    }

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "device": async_redact_data(device_info, TO_REDACT),
        "coordinator_data": async_redact_data(coordinator.data, TO_REDACT),
        "last_update_success": coordinator.last_update_success,
    }
