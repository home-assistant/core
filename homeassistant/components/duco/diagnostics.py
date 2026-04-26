"""Diagnostics support for Duco."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import DucoConfigEntry

TO_REDACT = {
    CONF_HOST,
    "mac",
    "host_name",
    "serial_board_box",
    "serial_board_comm",
    "serial_duco_box",
    "serial_duco_comm",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DucoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    board = asdict(coordinator.board_info)
    board.pop("time")

    lan_info, duco_diags, write_remaining = await asyncio.gather(
        coordinator.client.async_get_lan_info(),
        coordinator.client.async_get_diagnostics(),
        coordinator.client.async_get_write_req_remaining(),
    )

    return async_redact_data(
        {
            "entry_data": entry.data,
            "board_info": board,
            "lan_info": asdict(lan_info),
            "nodes": {
                str(node_id): asdict(node)
                for node_id, node in coordinator.data.nodes.items()
            },
            "duco_diagnostics": [asdict(d) for d in duco_diags],
            "write_requests_remaining": write_remaining,
        },
        TO_REDACT,
    )
