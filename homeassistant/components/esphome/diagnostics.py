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

CONF_MAC_ADDRESS = "mac_address"

REDACT_KEYS = {CONF_NOISE_PSK, CONF_PASSWORD, CONF_MAC_ADDRESS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ESPHomeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {}

    diag["config"] = config_entry.as_dict()

    entry_data = config_entry.runtime_data

    if (storage_data := await entry_data.store.async_load()) is not None:
        diag["storage_data"] = storage_data

    if (
        config_entry.unique_id
        and (scanner := async_scanner_by_source(hass, config_entry.unique_id.upper()))
        and (bluetooth_device := entry_data.bluetooth_device)
    ):
        diag["bluetooth"] = {
            "connections_free": bluetooth_device.ble_connections_free,
            "connections_limit": bluetooth_device.ble_connections_limit,
            "available": bluetooth_device.available,
            "scanner": await scanner.async_diagnostics(),
        }

    if dashboard := async_get_dashboard(hass):
        diag["dashboard"] = dashboard.addon_slug

    return async_redact_data(diag, REDACT_KEYS)
