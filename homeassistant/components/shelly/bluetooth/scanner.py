"""Bluetooth scanner for shelly."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.bluetooth import BaseRemoteHaScanner
from homeassistant.core import callback

from .decode import parse_ble_event

_LOGGER = logging.getLogger(__name__)

BLE_SCAN_RESULT_EVENT = "ble.scan_result"


class ShellyBLEScanner(BaseRemoteHaScanner):
    """Scanner for shelly."""

    @callback
    def async_on_event(self, event: dict[str, Any]) -> None:
        """Process an event from the shelly and ignore if its not a ble.scan_result."""
        if event.get("event") != BLE_SCAN_RESULT_EVENT:
            return
        try:
            parsed = parse_ble_event(*event["data"])
        except Exception as err:  # pylint: disable=broad-except
            # Broad exception catch because we have no control over the
            # data that is coming in.
            _LOGGER.error("Failed to parse BLE event: %s", err, exc_info=True)

        self._async_on_advertisement(*parsed)
