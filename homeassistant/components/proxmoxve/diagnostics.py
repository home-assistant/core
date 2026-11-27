"""Diagnostics support for Proxmox VE."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN_SECRET, CONF_USER
from .coordinator import ProxmoxConfigEntry

TO_REDACT = [
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_HOST,
    CONF_TOKEN_SECRET,
    CONF_USER,
    "upid",
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ProxmoxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Proxmox VE config entry."""

    runtime_data = config_entry.runtime_data
    devices = {
        node: asdict(node_data) for node, node_data in runtime_data.status.data.items()
    }
    # The full list of pending package updates is too noisy for diagnostics
    software = {
        node: {
            "version": asdict(info.version),
            "pending_updates": None if info.update is None else len(info.update),
        }
        for node, info in runtime_data.software.data.items()
    }

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "devices": async_redact_data(devices, TO_REDACT),
        "software": software,
    }
