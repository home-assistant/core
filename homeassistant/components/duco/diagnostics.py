"""Diagnostics support for Duco."""

from dataclasses import asdict
from typing import Any

from duco_connectivity.exceptions import DucoConnectionError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import DucoConfigEntry

# MAC addresses and serial numbers are redacted because a Duco installer or
# manufacturer could cross-reference them against an installation registry to
# identify the physical location of the device.
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
    # `time` is a Unix epoch timestamp of the last board
    # info fetch; not useful for support triage.
    board.pop("time")
    if board["public_api_version"] is None:
        board.pop("public_api_version")
    if board["software_version"] is None:
        board.pop("software_version")

    try:
        api_info_obj = await coordinator.client.async_get_api_info()
        lan_info = await coordinator.client.async_get_lan_info()
        duco_diags = await coordinator.client.async_get_diagnostics()
        write_remaining = await coordinator.client.async_get_write_requests_remaining()
    except DucoConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from err

    api_info: dict[str, Any] = {"public_api_version": api_info_obj.public_api_version}
    if api_info_obj.reported_api_version is not None:
        api_info["reported_api_version"] = api_info_obj.reported_api_version

    return async_redact_data(
        {
            "entry_data": entry.data,
            "board_info": board,
            "api_info": api_info,
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
