"""The ssdp integration websocket apis."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Final

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import DOMAIN, SSDP_SCANNER
from .scanner import Scanner, SsdpChange


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the ssdp websocket API."""
    websocket_api.async_register_command(hass, ws_subscribe_discovery)


FIELD_SSDP_ST: Final = "ssdp_st"
FIELD_SSDP_LOCATION: Final = "ssdp_location"


def serialize_service_info(service_info: SsdpServiceInfo) -> dict[str, Any]:
    """Serialize a SsdpServiceInfo object."""
    return asdict(service_info)


class _DiscoverySubscription:
    """Class to hold and manage the subscription data."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        ws_msg_id: int,
        scanner: Scanner,
    ) -> None:
        """Initialize the subscription data."""
        self.hass = hass
        self.ws_msg_id = ws_msg_id
        self.connection = connection
        self.scanner = scanner
        self._job = HassJob(self._async_on_data)

    async def async_start(self) -> None:
        """Start the subscription."""
        connection = self.connection
        cancel_adv_callback = await self.scanner.async_register_callback(
            self._job, None
        )
        connection.subscriptions[self.ws_msg_id] = cancel_adv_callback
        self.connection.send_message(
            json_bytes(websocket_api.result_message(self.ws_msg_id))
        )

    @callback
    def _async_on_data(self, info: SsdpServiceInfo, change: SsdpChange) -> None:
        if change is SsdpChange.BYEBYE:
            self._async_removed(info)
        else:
            self._async_added(info)

    def _async_event_message(self, message: dict[str, Any]) -> None:
        self.connection.send_message(
            json_bytes(websocket_api.event_message(self.ws_msg_id, message))
        )

    def _async_added(self, service_info: SsdpServiceInfo) -> None:
        self._async_event_message({"add": [asdict(service_info)]})

    def _async_removed(self, service_info: SsdpServiceInfo) -> None:
        self._async_event_message(
            {
                "remove": [
                    {
                        FIELD_SSDP_ST: service_info.ssdp_st,
                        FIELD_SSDP_LOCATION: service_info.ssdp_location,
                    }
                ]
            }
        )


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
    await _DiscoverySubscription(hass, connection, msg["id"], scanner).async_start()
