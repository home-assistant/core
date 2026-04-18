"""Diagnostics support for UniFi Access."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import UnifiAccessConfigEntry

TO_REDACT = {CONF_API_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: UnifiAccessConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator_data": {
            "doors": {
                door_id: door.model_dump(mode="json")
                for door_id, door in data.doors.items()
            },
            "emergency": data.emergency.model_dump(mode="json"),
            "door_lock_rules": {
                door_id: rule.model_dump(mode="json")
                for door_id, rule in data.door_lock_rules.items()
            },
            "unconfirmed_lock_rule_doors": sorted(data.unconfirmed_lock_rule_doors),
            "supports_lock_rules": data.supports_lock_rules,
            "lock_rule_support_complete": data.lock_rule_support_complete,
            "door_thumbnails": {
                door_id: thumb.model_dump(mode="json")
                for door_id, thumb in data.door_thumbnails.items()
            },
        },
    }
