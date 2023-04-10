"""Websocket API for OTBR."""
from typing import TYPE_CHECKING

import python_otbr_api

from homeassistant.components.websocket_api import (
    ActiveConnection,
    async_register_command,
    async_response,
    websocket_command,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_CHANNEL, DOMAIN

if TYPE_CHECKING:
    from . import OTBRData


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the OTBR Websocket API."""
    async_register_command(hass, websocket_info)
    async_register_command(hass, websocket_create_network)


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


@websocket_command(
    {
        "type": "otbr/create_network",
    }
)
@async_response
async def websocket_create_network(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict
) -> None:
    """Create a new Thread network."""
    if DOMAIN not in hass.data:
        connection.send_error(msg["id"], "not_loaded", "No OTBR API loaded")
        return

    # We currently have no way to know which channel zha is using, assume it's
    # the default
    zha_channel = DEFAULT_CHANNEL

    data: OTBRData = hass.data[DOMAIN]

    try:
        await data.set_enabled(False)
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "set_enabled_failed", str(exc))
        return

    try:
        await data.create_active_dataset(
            python_otbr_api.OperationalDataSet(
                channel=zha_channel, network_name="home-assistant"
            )
        )
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "create_active_dataset_failed", str(exc))
        return

    try:
        await data.set_enabled(True)
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "set_enabled_failed", str(exc))
        return

    connection.send_result(msg["id"])
