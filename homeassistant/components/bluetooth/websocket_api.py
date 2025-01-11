"""The bluetooth integration websocket apis."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import lru_cache, partial
import time
from typing import Any

from habluetooth import BluetoothScanningMode
from home_assistant_bluetooth import BluetoothServiceInfoBleak
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.json import json_bytes

from .api import _get_manager, async_register_callback
from .match import BluetoothCallbackMatcher
from .models import BluetoothChange


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the bluetooth websocket API."""
    websocket_api.async_register_command(hass, ws_subscribe_advertisements)


@lru_cache(maxsize=1024)
def serialize_service_info(
    service_info: BluetoothServiceInfoBleak, time_diff: float
) -> dict[str, Any]:
    """Serialize a BluetoothServiceInfoBleak object."""
    return {
        "name": service_info.name,
        "address": service_info.address,
        "rssi": service_info.rssi,
        "manufacturer_data": {
            str(manufacturer_id): manufacturer_data.hex()
            for manufacturer_id, manufacturer_data in service_info.manufacturer_data.items()
        },
        "service_data": {
            service_uuid: service_data.hex()
            for service_uuid, service_data in service_info.service_data.items()
        },
        "service_uuids": service_info.service_uuids,
        "source": service_info.source,
        "connectable": service_info.connectable,
        "time": service_info.time + time_diff,
        "tx_power": service_info.tx_power,
    }


class _AdvertisementSubscription:
    """Class to hold and manage the subscription data."""

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
        self.pending = True
        # Keep time_diff precise to 2 decimal places
        # so the cached serialization can be reused,
        # however we still want to calculate it each
        # subscription in case the system clock is wrong
        # and gets corrected.
        self.time_diff = round(time.time() - time.monotonic(), 2)

    @callback
    def _async_unsubscribe(
        self, cancel_callbacks: tuple[Callable[[], None], ...]
    ) -> None:
        """Unsubscribe the callback."""
        for cancel_callback in cancel_callbacks:
            cancel_callback()

    @callback
    def async_start(self) -> None:
        """Start the subscription."""
        connection = self.connection
        cancel_adv_callback = async_register_callback(
            self.hass,
            self._async_on_advertisement,
            self.match_dict,
            BluetoothScanningMode.PASSIVE,
        )
        cancel_disappeared_callback = _get_manager(
            self.hass
        ).async_register_disappeared_callback(self._async_removed)
        connection.subscriptions[self.ws_msg_id] = partial(
            self._async_unsubscribe, (cancel_adv_callback, cancel_disappeared_callback)
        )
        self.pending = False
        self.connection.send_message(
            json_bytes(websocket_api.result_message(self.ws_msg_id))
        )
        self._async_added(self.pending_service_infos)
        self.pending_service_infos.clear()

    def _async_added(self, service_infos: Iterable[BluetoothServiceInfoBleak]) -> None:
        self.connection.send_message(
            json_bytes(
                websocket_api.event_message(
                    self.ws_msg_id,
                    {
                        "add": [
                            serialize_service_info(service_info, self.time_diff)
                            for service_info in service_infos
                        ]
                    },
                )
            )
        )

    def _async_removed(self, address: str) -> None:
        self.connection.send_message(
            json_bytes(
                websocket_api.event_message(
                    self.ws_msg_id,
                    {
                        "remove": [
                            {
                                "address": address,
                            }
                        ]
                    },
                )
            )
        )

    @callback
    def _async_on_advertisement(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Handle the callback."""
        if self.pending:
            self.pending_service_infos.append(service_info)
            return
        self._async_added((service_info,))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "bluetooth/subscribe_advertisements",
    }
)
@websocket_api.async_response
async def ws_subscribe_advertisements(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe advertisements websocket command."""
    _AdvertisementSubscription(
        hass, connection, msg["id"], BluetoothCallbackMatcher(connectable=False)
    ).async_start()
