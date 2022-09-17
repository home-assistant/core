"""Tracking for iBeacon devices."""
from __future__ import annotations

from ibeacon_ble import parse

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    SIGNAL_IBEACON_DEVICE_NEW,
    SIGNAL_IBEACON_DEVICE_SEEN,
    SIGNAL_IBEACON_DEVICE_UNAVAILABLE,
)


def signal_unavailable(unique_id: str) -> str:
    """Signal for the device going unavailable."""
    return f"{SIGNAL_IBEACON_DEVICE_UNAVAILABLE}_{unique_id}"


def signal_seen(unique_id: str) -> str:
    """Signal for the device being seen."""
    return f"{SIGNAL_IBEACON_DEVICE_SEEN}_{unique_id}"


class IBeaconScanner:
    """Set up the iBeacon Scanner."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the scanner."""
        self.hass = hass
        self._update_cancel: CALLBACK_TYPE | None = None
        self._unique_id_unavailable: dict[str, dict[str, CALLBACK_TYPE]] = {}
        self._address_to_unique_id: dict[str, set[str]] = {}

    @callback
    def _async_handle_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Handle unavailable devices."""
        address = service_info.address
        unique_ids = self._address_to_unique_id.pop(service_info.address)
        for unique_id in unique_ids:
            address_callbacks = self._unique_id_unavailable[unique_id]
            # Cancel the unavailable tracker
            address_callbacks.pop(address)()
            # If its the last beacon broadcasting that unique_id, its now unavailable
            if not address_callbacks:
                async_dispatcher_send(self.hass, signal_unavailable(unique_id))

    @callback
    def _async_update_ibeacon(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a bluetooth callback."""
        if not (parsed := parse(service_info)):
            return
        address = service_info.address
        uuid = parsed.uuid
        major = parsed.major
        minor = parsed.minor
        unique_id = f"{uuid}_{major}_{minor}"
        new = False
        if unique_id not in self._unique_id_unavailable:
            self._unique_id_unavailable[unique_id] = {}
            new = True
        unavailable_trackers = self._unique_id_unavailable[unique_id]
        if address not in unavailable_trackers:
            self._address_to_unique_id.setdefault(address, set()).add(unique_id)
            unavailable_trackers[address] = bluetooth.async_track_unavailable(
                self.hass, self._async_handle_unavailable, address
            )
        rssi_by_address: dict[str, int] = {}
        for address in unavailable_trackers:
            device = bluetooth.async_ble_device_from_address(self.hass, address)
            rssi_by_address[address] = device.rssi if device else None
        if new:
            async_dispatcher_send(
                self.hass, SIGNAL_IBEACON_DEVICE_NEW, unique_id, parsed, rssi_by_address
            )
        else:
            async_dispatcher_send(
                self.hass, signal_seen(unique_id), parsed, rssi_by_address
            )

    @callback
    def async_stop(self) -> None:
        """Stop the scanner."""
        if self._update_cancel:
            self._update_cancel()
            self._update_cancel = None
        for address_cancels in self._unique_id_unavailable.values():
            for cancel in address_cancels.values():
                cancel()
        self._unique_id_unavailable.clear()

    @callback
    def async_start(self) -> None:
        """Start the scanner."""
        self._update_cancel = bluetooth.async_register_callback(
            self.hass,
            self._async_update_ibeacon,
            BluetoothCallbackMatcher(
                connectable=False, manufacturer_id=76, manufacturer_data_start=[2, 21]
            ),  # We will take data from any source
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
