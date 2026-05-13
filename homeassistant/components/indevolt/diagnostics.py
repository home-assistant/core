"""Diagnostics support for Indevolt integration."""

from typing import Any

from indevolt_api import IndevoltBattery, IndevoltSystem

from homeassistant.components.diagnostics import REDACTED, async_redact_data
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


def _redact_mac(mac_address: str | None) -> str | None:
    """Redact the device-specific part of a MAC address (keep OUI, used for discovery)."""
    if not mac_address:
        return mac_address

    # format_mac normalises to aa:bb:cc:dd:ee:ff; fall back to REDACTED for
    # any unrecognised format that passed through unchanged.
    parts = mac_address.split(":")
    if len(parts) == 6:
        return ":".join([*parts[:3], "XX", "XX", "XX"])

    return REDACTED


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
        "mac_address": _redact_mac(coordinator.mac_address),
    }

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "device": async_redact_data(device_info, TO_REDACT),
        "coordinator_data": async_redact_data(coordinator.data, TO_REDACT),
        "last_update_success": coordinator.last_update_success,
    }
