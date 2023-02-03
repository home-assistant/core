"""The thread websocket API."""
from __future__ import annotations

from typing import Any

from python_otbr_api.tlv_parser import TLVError
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from . import dataset_store


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the sensor websocket API."""
    websocket_api.async_register_command(hass, ws_add_dataset)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "thread/add_dataset_tlv",
        vol.Required("source"): str,
        vol.Required("tlv"): str,
    }
)
@websocket_api.async_response
async def ws_add_dataset(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add a thread dataset."""
    source = msg["source"]
    tlv = msg["tlv"]

    try:
        await dataset_store.async_add_dataset(hass, source, tlv)
    except TLVError as exc:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_INVALID_FORMAT, str(exc)
        )
        return

    connection.send_result(msg["id"])
