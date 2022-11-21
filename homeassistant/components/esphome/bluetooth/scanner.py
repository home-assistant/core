"""Bluetooth scanner for esphome."""
from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
import re

from aioesphomeapi import BluetoothLEAdvertisement

from homeassistant.components.bluetooth import (
    BaseHaRemoteScanner,
    BluetoothServiceInfoBleak,
    HaBluetoothConnector,
)
from homeassistant.core import HomeAssistant, callback

TWO_CHAR = re.compile("..")


class ESPHomeScanner(BaseHaRemoteScanner):
    """Scanner for esphome."""

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
        connector: HaBluetoothConnector,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        super().__init__(hass, scanner_id, new_info_callback, connector, connectable)
        self._connecting = 0

    @contextmanager
    def connecting(self) -> Generator[None, None, None]:
        """Context manager to track connecting state."""
        self._connecting += 1
        yield
        self._connecting -= 1

    @property
    def scanning(self) -> bool:
        """Return if the scanner is scanning."""
        # If we are connecting, we are not scanning
        return not self._connecting

    @callback
    def async_on_advertisement(self, adv: BluetoothLEAdvertisement) -> None:
        """Call the registered callback."""
        address = ":".join(TWO_CHAR.findall("%012X" % adv.address))  # must be upper
        self._async_on_advertisement(
            address,
            adv.rssi,
            adv.name,
            adv.service_uuids,
            adv.service_data,
            adv.manufacturer_data,
            None,
        )
