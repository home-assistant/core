"""Bluetooth scanner for shelly."""
from __future__ import annotations

from base64 import b64decode
import logging
from typing import Any

from bluetooth_data_tools import parse_advertisement_data

from homeassistant.components.bluetooth import BaseRemoteHaScanner
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

BLE_SCAN_RESULT_EVENT = "ble.scan_result"


class ShellyBLEScanner(BaseRemoteHaScanner):
    """Scanner for shelly."""

    @callback
    def async_on_event(self, event: dict[str, Any]) -> None:
        """Process an event from the shelly and ignore if its not a ble.scan_result."""
        if (
            event.get("event") != BLE_SCAN_RESULT_EVENT
            or not (data := event.get("data"))
            or len(data) != 4
        ):
            return

        address: str = data[0]
        rssi: int = data[1]
        advertisement_data_b64: str = data[2]
        scan_response_b64: str = data[3]

        try:
            parsed = parse_advertisement_data(
                (b64decode(advertisement_data_b64), b64decode(scan_response_b64))
            )
        except Exception as err:  # pylint: disable=broad-except
            # Broad exception catch because we have no
            # control over the data that is coming in.
            _LOGGER.error("Failed to parse BLE event: %s", err, exc_info=True)

        self._async_on_advertisement(
            address.upper(),
            rssi,
            parsed.local_name,
            parsed.service_uuids,
            parsed.service_data,
            parsed.manufacturer_data,
            parsed.tx_power,
        )
