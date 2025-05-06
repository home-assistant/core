"""The ssdp integration websocket apis."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Final

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    SsdpServiceInfo,
)

from .const import DOMAIN, SSDP_SCANNER
from .scanner import Scanner, SsdpChange

FIELD_SSDP_ST: Final = "ssdp_st"
FIELD_SSDP_LOCATION: Final = "ssdp_location"


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the ssdp websocket API."""
    websocket_api.async_register_command(hass, ws_subscribe_discovery)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ssdp/subscribe_discovery",
    }
)
@websocket_api.async_response
async def ws_subscribe_discovery(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe advertisements websocket command."""
    scanner: Scanner = hass.data[DOMAIN][SSDP_SCANNER]
    msg_id: int = msg["id"]

    def _async_event_message(message: dict[str, Any]) -> None:
        connection.send_message(
            json_bytes(websocket_api.event_message(msg_id, message))
        )

    @callback
    def _async_on_data(info: SsdpServiceInfo, change: SsdpChange) -> None:
        if change is not SsdpChange.BYEBYE:
            _async_event_message(
                {
                    "add": [
                        {"name": info.upnp.get(ATTR_UPNP_FRIENDLY_NAME), **asdict(info)}
                    ]
                }
            )
            return
        remove_msg = {
            FIELD_SSDP_ST: info.ssdp_st,
            FIELD_SSDP_LOCATION: info.ssdp_location,
        }
        _async_event_message({"remove": [remove_msg]})

    job = HassJob(_async_on_data)
    connection.send_message(json_bytes(websocket_api.result_message(msg_id)))
    connection.subscriptions[msg_id] = await scanner.async_register_callback(job, None)
