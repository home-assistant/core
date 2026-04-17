"""Diagnostics support for Wibeee integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import WibeeeConfigEntry

TO_REDACT = {CONF_HOST, "mac_address", "mac_addr", "mac"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: WibeeeConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data

    device_info = runtime.device_info
    coordinator = runtime.coordinator

    # Gather push server config if available
    push_config: dict[str, Any] | None = None
    try:
        push_config = await runtime.api.async_get_push_server_config()
    except Exception:  # noqa: BLE001
        push_config = {"error": "Could not retrieve push server config"}

    # Gather device configuration variables from values.xml and status.xml
    device_diagnostics: dict[str, Any] = {}
    try:
        device_diagnostics = await runtime.api.async_fetch_device_diagnostics()
    except Exception:  # noqa: BLE001
        device_diagnostics = {"error": "Could not retrieve device diagnostics"}

    diag: dict[str, Any] = {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "device": {
            "wibeee_id": device_info.wibeee_id,
            "mac_addr": "**REDACTED**",
            "model": device_info.model,
            "firmware_version": device_info.firmware_version,
            "ip_addr": "**REDACTED**",
        },
        "device_config": device_diagnostics,
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "data": _redact_coordinator_data(coordinator.data),
        },
        "push_server_config": (
            async_redact_data(push_config, {"server_ip"}) if push_config else None
        ),
    }

    return diag


def _redact_coordinator_data(
    data: Any,
) -> dict[str, dict[str, str]] | None:
    """Return coordinator data (sensor values are not sensitive)."""
    if data is None:
        return None
    return {phase: dict(sensors) for phase, sensors in data.items()}
