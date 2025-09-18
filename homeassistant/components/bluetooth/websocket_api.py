"""The bluetooth integration websocket apis."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import lru_cache, partial
import time
from typing import Any

from habluetooth import (
    BaseHaScanner,
    BluetoothScanningMode,
    HaBluetoothSlotAllocations,
    HaScannerModeChange,
    HaScannerRegistration,
    HaScannerRegistrationEvent,
)
from home_assistant_bluetooth import BluetoothServiceInfoBleak
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.json import json_bytes

from .api import _get_manager, async_register_callback
from .const import DOMAIN
from .match import BluetoothCallbackMatcher
from .models import BluetoothChange
from .util import InvalidConfigEntryID, InvalidSource, config_entry_id_to_source


@callback
def _async_get_source_from_config_entry(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg_id: int,
    config_entry_id: str | None,
    validate_source: bool = True,
) -> str | None:
    """Get source from config entry id.

    Returns None if no config_entry_id provided or on error (after sending error response).
    If validate_source is True, also validates that the scanner exists.
    """
    if not config_entry_id:
        return None

    if validate_source:
        # Use the full validation that checks if scanner exists
        try:
            return config_entry_id_to_source(hass, config_entry_id)
        except InvalidConfigEntryID as err:
            connection.send_error(msg_id, "invalid_config_entry_id", str(err))
            return None
        except InvalidSource as err:
            connection.send_error(msg_id, "invalid_source", str(err))
            return None

    # Just check if config entry exists and belongs to bluetooth
    if (
        not (entry := hass.config_entries.async_get_entry(config_entry_id))
        or entry.domain != DOMAIN
    ):
        connection.send_error(
            msg_id,
            "invalid_config_entry_id",
            f"Config entry {config_entry_id} not found",
        )
        return None
    return entry.unique_id


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the bluetooth websocket API."""
    websocket_api.async_register_command(hass, ws_subscribe_advertisements)
    websocket_api.async_register_command(hass, ws_subscribe_connection_allocations)
    websocket_api.async_register_command(hass, ws_subscribe_scanner_details)
    websocket_api.async_register_command(hass, ws_subscribe_scanner_state)


@lru_cache(maxsize=1024)
def serialize_service_info(
    service_info: BluetoothServiceInfoBleak, time_diff: float
) -> dict[str, Any]:
    """Serialize a BluetoothServiceInfoBleak object.

    The raw field is included for:
    1. Debugging - to see the actual advertisement packet
    2. Data freshness - manufacturer_data and service_data are aggregated
       across multiple advertisements, raw shows the latest packet only
    """
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
        "raw": service_info.raw.hex() if service_info.raw else None,
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

    def _async_event_message(self, message: dict[str, Any]) -> None:
        self.connection.send_message(
            json_bytes(websocket_api.event_message(self.ws_msg_id, message))
        )

    def _async_added(self, service_infos: Iterable[BluetoothServiceInfoBleak]) -> None:
        self._async_event_message(
            {
                "add": [
                    serialize_service_info(service_info, self.time_diff)
                    for service_info in service_infos
                ]
            }
        )

    def _async_removed(self, address: str) -> None:
        self._async_event_message({"remove": [{"address": address}]})

    @callback
    def _async_on_advertisement(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Handle the callback."""
        if self.pending:
            self.pending_service_infos.append(service_info)
            return
        self._async_added((service_info,))


@websocket_api.require_admin
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


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "bluetooth/subscribe_connection_allocations",
        vol.Optional("config_entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_subscribe_connection_allocations(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe advertisements websocket command."""
    ws_msg_id = msg["id"]
    config_entry_id = msg.get("config_entry_id")
    source = _async_get_source_from_config_entry(
        hass, connection, ws_msg_id, config_entry_id
    )
    if config_entry_id and source is None:
        return  # Error already sent by helper

    def _async_allocations_changed(allocations: HaBluetoothSlotAllocations) -> None:
        connection.send_message(
            json_bytes(websocket_api.event_message(ws_msg_id, [allocations]))
        )

    manager = _get_manager(hass)
    connection.subscriptions[ws_msg_id] = manager.async_register_allocation_callback(
        _async_allocations_changed, source
    )
    connection.send_message(json_bytes(websocket_api.result_message(ws_msg_id)))
    if current_allocations := manager.async_current_allocations(source):
        connection.send_message(
            json_bytes(websocket_api.event_message(ws_msg_id, current_allocations))
        )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "bluetooth/subscribe_scanner_details",
        vol.Optional("config_entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_subscribe_scanner_details(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe scanner details websocket command."""
    ws_msg_id = msg["id"]
    config_entry_id = msg.get("config_entry_id")
    source = _async_get_source_from_config_entry(
        hass, connection, ws_msg_id, config_entry_id, validate_source=False
    )
    if config_entry_id and source is None:
        return  # Error already sent by helper

    def _async_event_message(message: dict[str, Any]) -> None:
        connection.send_message(
            json_bytes(websocket_api.event_message(ws_msg_id, message))
        )

    def _async_registration_changed(registration: HaScannerRegistration) -> None:
        added_event = HaScannerRegistrationEvent.ADDED
        event_type = "add" if registration.event == added_event else "remove"
        _async_event_message({event_type: [registration.scanner.details]})

    manager = _get_manager(hass)
    connection.subscriptions[ws_msg_id] = (
        manager.async_register_scanner_registration_callback(
            _async_registration_changed, source
        )
    )
    connection.send_message(json_bytes(websocket_api.result_message(ws_msg_id)))
    if (scanners := manager.async_current_scanners()) and (
        matching_scanners := [
            scanner.details
            for scanner in scanners
            if source is None or scanner.source == source
        ]
    ):
        _async_event_message({"add": matching_scanners})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "bluetooth/subscribe_scanner_state",
        vol.Optional("config_entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_subscribe_scanner_state(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle subscribe scanner state websocket command."""
    ws_msg_id = msg["id"]
    config_entry_id = msg.get("config_entry_id")
    source = _async_get_source_from_config_entry(
        hass, connection, ws_msg_id, config_entry_id, validate_source=False
    )
    if config_entry_id and source is None:
        return  # Error already sent by helper

    @callback
    def _async_send_scanner_state(
        scanner: BaseHaScanner,
        current_mode: BluetoothScanningMode | None,
        requested_mode: BluetoothScanningMode | None,
    ) -> None:
        payload = {
            "source": scanner.source,
            "adapter": scanner.adapter,
            "current_mode": current_mode.value if current_mode else None,
            "requested_mode": requested_mode.value if requested_mode else None,
        }
        connection.send_message(
            json_bytes(
                websocket_api.event_message(
                    ws_msg_id,
                    payload,
                )
            )
        )

    @callback
    def _async_scanner_state_changed(mode_change: HaScannerModeChange) -> None:
        _async_send_scanner_state(
            mode_change.scanner,
            mode_change.current_mode,
            mode_change.requested_mode,
        )

    manager = _get_manager(hass)
    connection.subscriptions[ws_msg_id] = (
        manager.async_register_scanner_mode_change_callback(
            _async_scanner_state_changed, source
        )
    )
    connection.send_message(json_bytes(websocket_api.result_message(ws_msg_id)))

    # Send initial state for all matching scanners
    for scanner in manager.async_current_scanners():
        if source is None or scanner.source == source:
            _async_send_scanner_state(
                scanner,
                scanner.current_mode,
                scanner.requested_mode,
            )
