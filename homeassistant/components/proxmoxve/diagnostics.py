"""Diagnostics support for Proxmox VE."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import ProxmoxConfigEntry

TO_REDACT = [CONF_USERNAME, CONF_PASSWORD, CONF_HOST]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ProxmoxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Proxmox VE config entry."""

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "devices": {
            node: asdict(node_data)
            for node, node_data in config_entry.runtime_data.data.items()
        },
    }
