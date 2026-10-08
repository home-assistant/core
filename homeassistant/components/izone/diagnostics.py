"""Diagnostics support for iZone."""

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import IZoneConfigEntry
from .discovery import DATA_DISCOVERY_SERVICE

TO_REDACT = {
    CONF_HOST,
    "device_ip",
    "source_ip",
}


def _redact_data(data: Any) -> Any:
    """Redact host keys and scrub those host values from sibling strings."""
    if isinstance(data, list):
        return [_redact_data(item) for item in data]
    if isinstance(data, Mapping):
        hosts = {
            value
            for key, value in data.items()
            if key in TO_REDACT and isinstance(value, str)
        }
        result: dict[Any, Any] = {}
        for key, value in data.items():
            if key in TO_REDACT:
                result[key] = REDACTED
                continue
            redacted = _redact_data(value)
            if hosts and isinstance(redacted, str):
                for host in hosts:
                    redacted = redacted.replace(host, REDACTED)
            result[key] = redacted
        return result
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

    return _redact_data(
        {
            "entry": {
                **dict(entry.data),
                "unique_id": entry.unique_id,
            },
            "discovery": discovery,
            "controller": controller.dump_state(),
        }
    )
