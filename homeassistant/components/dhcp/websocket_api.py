"""The dhcp integration websocket apis."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.json import json_bytes

from .const import HOSTNAME, IP_ADDRESS
from .helpers import (
    async_get_address_data_internal,
    async_register_dhcp_callback_internal,
)
from .models import DHCPAddressData


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the DHCP websocket API."""
    websocket_api.async_register_command(hass, ws_subscribe_discovery)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "dhcp/subscribe_discovery",
    }
)
@websocket_api.async_response
async def ws_subscribe_discovery(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe discovery websocket command."""
    ws_msg_id: int = msg["id"]

    def _async_send(address_data: dict[str, DHCPAddressData]) -> None:
        connection.send_message(
            json_bytes(
                websocket_api.event_message(
                    ws_msg_id,
                    {
                        "add": [
                            {
                                "mac_address": dr.format_mac(mac_address).upper(),
                                "hostname": data[HOSTNAME],
                                "ip_address": data[IP_ADDRESS],
                            }
                            for mac_address, data in address_data.items()
                        ]
                    },
                )
            )
        )

    unsub = async_register_dhcp_callback_internal(hass, _async_send)
    connection.subscriptions[ws_msg_id] = unsub
    connection.send_message(json_bytes(websocket_api.result_message(ws_msg_id)))
    _async_send(async_get_address_data_internal(hass))
