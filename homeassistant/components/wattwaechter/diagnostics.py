"""Diagnostics support for the WattWächter Plus integration."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import WattwaechterConfigEntry

TO_REDACT = {CONF_TOKEN}
TO_REDACT_DEVICE = {"mac"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WattwaechterConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "config": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "coordinator_data": {
            "meter": (
                dataclasses.asdict(coordinator.data.meter)
                if coordinator.data and coordinator.data.meter
                else None
            ),
            "system": (
                dataclasses.asdict(coordinator.data.system)
                if coordinator.data
                else None
            ),
        },
        "device_info": async_redact_data(
            {
                "device_id": coordinator.device_id,
                "model": coordinator.model,
                "fw_version": coordinator.fw_version,
                "mac": coordinator.mac,
                "host": coordinator.host,
            },
            TO_REDACT_DEVICE,
        ),
    }
