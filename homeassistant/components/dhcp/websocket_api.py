"""The dhcp integration websocket apis."""

from __future__ import annotations

from typing import Any, TypedDict

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo as _DhcpServiceInfo

from .const import HOSTNAME, IP_ADDRESS
from .helpers import (
    async_get_address_data_internal,
    async_register_dhcp_callback_internal,
)


class DHCPDiscovery(TypedDict):
    """Typed dict for DHCP discovery."""

    mac_address: str
    hostname: str
    ip_address: str


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the DHCP websocket API."""
    websocket_api.async_register_command(hass, ws_subscribe_discovery)


def serialize_service_info(service_info: _DhcpServiceInfo) -> DHCPDiscovery:
    """Serialize a _DhcpServiceInfo object."""
    serialized: DHCPDiscovery = {
        "mac_address": service_info.macaddress.upper(),
        "hostname": service_info.hostname,
        "ip_address": service_info.ip,
    }
    return serialized


class _DiscoverySubscription:
    """Class to hold and manage the subscription data."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        ws_msg_id: int,
    ) -> None:
        """Initialize the subscription data."""
        self.hass = hass
        self.ws_msg_id = ws_msg_id
        self.connection = connection

    @callback
    def async_start(self) -> None:
        """Start the subscription."""
        connection = self.connection
        connection.subscriptions[self.ws_msg_id] = (
            async_register_dhcp_callback_internal(
                self.hass,
                self._async_on_discovery,
            )
        )
        connection.send_message(
            json_bytes(websocket_api.result_message(self.ws_msg_id))
        )
        self._async_send_current_address_data()

    def _async_event_message(self, message: dict[str, Any]) -> None:
        self.connection.send_message(
            json_bytes(websocket_api.event_message(self.ws_msg_id, message))
        )

    def _async_send_current_address_data(self) -> None:
        """Send the current address data."""
        address_data = async_get_address_data_internal(self.hass)
        self._async_event_message(
            {
                "add": [
                    {
                        "mac_address": dr.format_mac(mac_address).upper(),
                        "hostname": data[HOSTNAME],
                        "ip_address": data[IP_ADDRESS],
                    }
                    for mac_address, data in address_data.items()
                ]
            }
        )

    def _async_added(self, service_infos: list[_DhcpServiceInfo]) -> None:
        self._async_event_message(
            {
                "add": [
                    serialize_service_info(service_info)
                    for service_info in service_infos
                ]
            }
        )

    @callback
    def _async_on_discovery(self, service_info: _DhcpServiceInfo) -> None:
        """Handle the callback."""
        self._async_event_message({"add": [serialize_service_info(service_info)]})


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
    _DiscoverySubscription(hass, connection, msg["id"]).async_start()
