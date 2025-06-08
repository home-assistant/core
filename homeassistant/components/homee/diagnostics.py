"""Diagnostics for homee integration."""

import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import DOMAIN, HomeeConfigEntry

TO_REDACT = [CONF_PASSWORD, CONF_USERNAME, "latitude", "longitude", "wlan_ssid"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomeeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "settings": async_redact_data(entry.runtime_data.settings.raw_data, TO_REDACT),
        "devices": [{"node": node.raw_data} for node in entry.runtime_data.nodes],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: HomeeConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""

    # Extract node_id from the device identifiers
    identifiers_matches = re.search(
        r"[0-9,A-F]{12}-(\d{1,4})",
        next(
            identifier[1]
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
        ),
    )
    assert identifiers_matches is not None
    node_id = identifiers_matches.group(1)
    return {
        "homee node": entry.runtime_data.get_node_by_id(int(node_id)).raw_data,
    }
