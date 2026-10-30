"""Diagnostics support for Tesla Wall Connector."""

from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_SPLIT_PHASE,
    DEFAULT_SPLIT_PHASE,
    WALLCONNECTOR_DATA_LIFETIME,
    WALLCONNECTOR_DATA_VITALS,
    WALLCONNECTOR_DATA_WIFI_STATUS,
)
from .coordinator import WallConnectorConfigEntry

WIFI_STATUS_EXCLUDE = {"wifi_ssid", "wifi_infra_ip", "wifi_mac"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WallConnectorConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    data = runtime_data.update_coordinator.data
    return {
        "split_phase": entry.options.get(CONF_SPLIT_PHASE, DEFAULT_SPLIT_PHASE),
        "part_number": runtime_data.part_number,
        "firmware_version": runtime_data.firmware_version,
        "vitals": data[WALLCONNECTOR_DATA_VITALS].raw_data,
        "lifetime": data[WALLCONNECTOR_DATA_LIFETIME].raw_data,
        "wifi_status": {
            key: value
            for key, value in data[WALLCONNECTOR_DATA_WIFI_STATUS].raw_data.items()
            if key not in WIFI_STATUS_EXCLUDE
        },
    }
