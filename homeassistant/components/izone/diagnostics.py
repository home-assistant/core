"""Diagnostics support for iZone."""

from collections.abc import Mapping
import re
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import IZoneConfigEntry
from .discovery import DATA_DISCOVERY_SERVICE

TO_REDACT = {
    CONF_HOST,
    "device_ip",
    "source_ip",
}

_IPV4 = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")


def _redact_ipv4_strings(data: Any) -> Any:
    """Replace IPv4 literals embedded in strings (e.g. UDP ``IP_…`` payloads)."""
    if isinstance(data, str):
        return _IPV4.sub(str(REDACTED), data)
    if isinstance(data, list):
        return [_redact_ipv4_strings(item) for item in data]
    if isinstance(data, Mapping):
        return {key: _redact_ipv4_strings(value) for key, value in data.items()}
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IZoneConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = entry.runtime_data.controller

    discovery_slot = hass.data.get(DATA_DISCOVERY_SERVICE)
    if discovery_slot is not None and discovery_slot.runtime is not None:
        discovery: dict[str, Any] = {
            "running": True,
            **discovery_slot.runtime.service.dump_state(),
        }
    else:
        discovery = {"running": False}

    return _redact_ipv4_strings(
        async_redact_data(
            {
                "entry": {
                    **dict(entry.data),
                    "unique_id": entry.unique_id,
                },
                "discovery": discovery,
                "controller": controller.dump_state(),
            },
            TO_REDACT,
        )
    )
