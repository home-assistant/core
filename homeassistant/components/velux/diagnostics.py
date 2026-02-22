"""Diagnostics support for Velux."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import VeluxConfigEntry

TO_REDACT = {CONF_HOST, CONF_MAC, CONF_PASSWORD}
TO_REDACT_NODE = {"serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VeluxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    pyvlx = entry.runtime_data

    nodes: list[dict[str, Any]] = [
        async_redact_data(
            {
                "node_id": node.node_id,
                "name": node.name,
                "serial_number": node.serial_number,
                "type": type(node).__name__,
            },
            TO_REDACT_NODE,
        )
        for node in pyvlx.nodes
    ]

    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "connection": {
            "connected": pyvlx.connection.connected,
            "connection_count": pyvlx.connection.connection_counter,
        },
        "gateway": {
            "state": str(pyvlx.klf200.state) if pyvlx.klf200.state else None,
            "version": str(pyvlx.klf200.version) if pyvlx.klf200.version else None,
            "protocol_version": (
                str(pyvlx.klf200.protocol_version)
                if pyvlx.klf200.protocol_version
                else None
            ),
        },
        "nodes": nodes,
    }
