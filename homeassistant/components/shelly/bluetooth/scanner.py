"""Bluetooth scanner for shelly."""
from __future__ import annotations

from base64 import b64decode
import logging
from typing import Any

from bluetooth_data_tools import parse_advertisement_data

from homeassistant.components.bluetooth import BaseHaRemoteScanner
from homeassistant.core import callback

from .const import BLE_SCAN_RESULT_EVENT, BLE_SCAN_RESULT_VERSION

_LOGGER = logging.getLogger(__name__)


class ShellyBLEScanner(BaseHaRemoteScanner):
    """Scanner for shelly."""

    @callback
    def async_on_event(self, event: dict[str, Any]) -> None:
        """Process an event from the shelly and ignore if its not a ble.scan_result."""
        if (
            event.get("event") != BLE_SCAN_RESULT_EVENT
            or not (data := event.get("data"))
            or len(data) != 5
        ):
            return

        version: int = data[0]
        if version != BLE_SCAN_RESULT_VERSION:
            _LOGGER.warning("Unsupported BLE scan result version: %s", version)
            return

        address: str = data[1]
        rssi: int = data[2]
        advertisement_data_b64: str = data[3]
        scan_response_b64: str = data[4]

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
