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
    # Free-text tags that users may fill with personal details such as an address.
    "Tag1",
    "Tag2",
}


def _redact_data(data: Any) -> Any:
    """Redact sensitive keys and scrub those values from sibling strings."""
    if isinstance(data, list):
        return [_redact_data(item) for item in data]
    if isinstance(data, Mapping):
        secrets = {
            value
            for key, value in data.items()
            if key in TO_REDACT and isinstance(value, str) and value
        }
        result: dict[Any, Any] = {}
        for key, value in data.items():
            if key in TO_REDACT:
                result[key] = REDACTED
                continue
            redacted = _redact_data(value)
            if secrets and isinstance(redacted, str):
                for secret in secrets:
                    redacted = redacted.replace(secret, REDACTED)
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
