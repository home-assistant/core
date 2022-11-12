"""Bluetooth scanner for shelly."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.bluetooth import BaseRemoteHaScanner
from homeassistant.core import callback

from .decode import parse_ble_event

_LOGGER = logging.getLogger(__name__)


class ShellyBLEScanner(BaseRemoteHaScanner):
    """Scanner for shelly."""

    @callback
    def async_on_update(self, event: dict[str, Any]) -> None:
        """Handle device update."""
        try:
            address, rssi, adv_base64, scan_base64 = event["data"]
            name, manufacturer_data, service_data, service_uuids = parse_ble_event(
                address, adv_base64, scan_base64
            )
        except Exception as err:  # pylint: disable=broad-except
            # Broad exception catch because we have no control over the
            # data that is coming in.
            _LOGGER.error("Failed to parse BLE event: %s", err, exc_info=True)

        self._async_on_advertisement(
            address, rssi, name, service_uuids, service_data, manufacturer_data, None
        )
