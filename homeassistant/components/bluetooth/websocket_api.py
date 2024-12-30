"""The bluetooth integration websocket apis."""

from __future__ import annotations

from typing import Any, cast

from habluetooth import BluetoothScanningMode
from home_assistant_bluetooth import BluetoothServiceInfoBleak
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_bytes

from .api import async_register_callback
from .match import CONNECTABLE, BluetoothCallbackMatcher
from .models import BluetoothChange


class _AdvertismentSubscription:
    """Class to hold the subscription data."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        ws_msg_id: int,
        match_dict: BluetoothCallbackMatcher,
    ) -> None:
        """Initialize the subscription data."""
        self.hass = hass
        self.match_dict = match_dict
        self.pending_service_infos: list[BluetoothServiceInfoBleak] = []
        self.ws_msg_id = ws_msg_id
        self.connection = connection
        self.__call__ = self.pending_mode_callback

    def start(self) -> None:
        """Start the subscription."""
        connection = self.connection
        connection.send_message(websocket_api.result_message(self.ws_msg_id))
        connection.subscriptions[self.ws_msg_id] = async_register_callback(
            self.hass, self, self.match_dict, BluetoothScanningMode.PASSIVE
        )
        self.__call__ = self.live_mode_callback
        connection.send_message(
            json_bytes(
                websocket_api.event_message(
                    self.ws_msg_id,
                    [
                        service_info.as_dict()
                        for service_info in self.pending_service_infos
                    ],
                )
            )
        )
        self.pending_service_infos.clear()

    def live_mode_callback(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Handle the callback."""
        self.connection.send_message(
            json_bytes(
                websocket_api.event_message(self.ws_msg_id, [service_info.as_dict()])
            )
        )

    def pending_mode_callback(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Handle the callback."""
        self.pending_service_infos.append(service_info)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bluetooth/subscribe_advertisements",
        vol.Optional("match_dict"): dict,
    }
)
@websocket_api.async_response
async def ws_subscribe_advertisements(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe advertisements websocket command."""
    if "match_dict" in msg:
        match_dict = cast(BluetoothCallbackMatcher, msg["match_dict"])
    else:
        match_dict = {CONNECTABLE: False}
    _AdvertismentSubscription(hass, connection, msg["id"], match_dict).start()
