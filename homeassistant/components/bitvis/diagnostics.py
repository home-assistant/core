"""Diagnostics support for Bitvis Power Hub."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import BitvisConfigEntry

TO_REDACT: set[str] = {CONF_HOST, CONF_PORT, "mac_address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BitvisConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    diagnostics_data: dict[str, Any] = {
        "config_entry": {
            "title": entry.title,
            CONF_HOST: entry.data.get(CONF_HOST),
            CONF_PORT: entry.data.get(CONF_PORT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "has_sample_data": coordinator.data.sample is not None,
            "has_diagnostic_data": coordinator.data.diagnostic is not None,
        },
    }

    if coordinator.data.diagnostic is not None:
        diag = coordinator.data.diagnostic.diagnostic
        diagnostics_data["device_diagnostic"] = {
            "uptime_s": diag.uptime_s,
            "wifi_rssi_dbm": diag.wifi_rssi_dbm,
            "event_type": diag.type,
            "han_msg_successfully_parsed": diag.han_msg_successfully_parsed,
            "han_msg_buffer_overflow": diag.han_msg_buffer_overflow,
        }

        if diag.HasField("device_info"):
            device_info = diag.device_info
            diagnostics_data["device_info"] = {
                "mac_address": device_info.mac_address.hex()
                if device_info.mac_address
                else None,
                "model_name": device_info.model_name,
                "sw_version": device_info.sw_version,
                "hw_revision": device_info.hw_revision,
            }

    return async_redact_data(diagnostics_data, TO_REDACT)
