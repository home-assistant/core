"""Diagnostics support for ESPHome."""

from __future__ import annotations

from typing import Any

from homeassistant.components.bluetooth import async_scanner_by_source
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import CONF_NOISE_PSK
from .dashboard import async_get_dashboard
from .entry_data import ESPHomeConfigEntry

REDACT_KEYS = {CONF_NOISE_PSK, CONF_PASSWORD, "mac_address", "bluetooth_mac_address"}
CONFIGURED_DEVICE_KEYS = (
    "configuration",
    "current_version",
    "deployed_version",
    "loaded_integrations",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ESPHomeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {}

    diag["config"] = config_entry.as_dict()

    entry_data = config_entry.runtime_data
    device_info = entry_data.device_info

    if (storage_data := await entry_data.store.async_load()) is not None:
        diag["storage_data"] = storage_data

    if (
        device_info
        and (
            scanner_mac := device_info.bluetooth_mac_address or device_info.mac_address
        )
        and (scanner := async_scanner_by_source(hass, scanner_mac.upper()))
        and (bluetooth_device := entry_data.bluetooth_device)
    ):
        diag["bluetooth"] = {
            "connections_free": bluetooth_device.ble_connections_free,
            "connections_limit": bluetooth_device.ble_connections_limit,
            "available": bluetooth_device.available,
            "scanner": await scanner.async_diagnostics(),
        }

    diag_dashboard: dict[str, Any] = {"configured": False}
    diag["dashboard"] = diag_dashboard
    if dashboard := async_get_dashboard(hass):
        diag_dashboard["configured"] = True
        diag_dashboard["supports_update"] = dashboard.supports_update
        diag_dashboard["last_update_success"] = dashboard.last_update_success
        diag_dashboard["addon"] = dashboard.addon_slug
        diag_dashboard["devices"] = {
            name: {key: data.get(key) for key in CONFIGURED_DEVICE_KEYS}
            for name, data in dashboard.data.items()
        }

    return async_redact_data(diag, REDACT_KEYS)
