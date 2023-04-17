"""Websocket API for OTBR."""
from typing import TYPE_CHECKING

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_register_command,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

if TYPE_CHECKING:
    from . import OTBRData


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the OTBR Websocket API."""
    async_register_command(hass, websocket_info)


@websocket_command(
    {
        "type": "otbr/info",
    }
)
@async_response
async def websocket_info(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Get OTBR info."""
    if DOMAIN not in hass.data:
        connection.send_error(msg["id"], "not_loaded", "No OTBR API loaded")
        return

    data: OTBRData = hass.data[DOMAIN]

    try:
        dataset = await data.get_active_dataset_tlvs()
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "get_dataset_failed", str(exc))
        return

    connection.send_result(
        msg["id"],
        {
            "url": data.url,
            "active_dataset_tlvs": dataset.hex() if dataset else None,
        },
    )
