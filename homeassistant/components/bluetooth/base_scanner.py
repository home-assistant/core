"""Base classes for HA Bluetooth scanners for bluetooth."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bluetooth_adapters import DiscoveredDeviceAdvertisementData
from habluetooth import BaseHaRemoteScanner, BaseHaScanner, HaBluetoothConnector
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    callback as hass_callback,
)

from . import models


@dataclass(slots=True)
class BluetoothScannerDevice:
    """Data for a bluetooth device from a given scanner."""

    scanner: BaseHaScanner
    ble_device: BLEDevice
    advertisement: AdvertisementData


class HomeAssistantRemoteScanner(BaseHaRemoteScanner):
    """Home Assistant remote BLE scanner.

    This is the only object that should know about
    the hass object.
    """

    __slots__ = (
        "hass",
        "_storage",
        "_cancel_stop",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        scanner_id: str,
        name: str,
        new_info_callback: Callable[[BluetoothServiceInfoBleak], None],
        connector: HaBluetoothConnector | None,
        connectable: bool,
    ) -> None:
        """Initialize the scanner."""
        self.hass = hass
        assert models.MANAGER is not None
        self._storage = models.MANAGER.storage
        self._cancel_stop: CALLBACK_TYPE | None = None
        super().__init__(scanner_id, name, new_info_callback, connector, connectable)

    @hass_callback
    def async_setup(self) -> CALLBACK_TYPE:
        """Set up the scanner."""
        super().async_setup()
        if history := self._storage.async_get_advertisement_history(self.source):
            self._discovered_device_advertisement_datas = (
                history.discovered_device_advertisement_datas
            )
            self._discovered_device_timestamps = history.discovered_device_timestamps
            # Expire anything that is too old
            self._async_expire_devices()

        self._cancel_stop = self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, self._async_save_history
        )
        return self._unsetup

    @hass_callback
    def _unsetup(self) -> None:
        super()._unsetup()
        self._async_save_history()
        if self._cancel_stop:
            self._cancel_stop()
            self._cancel_stop = None

    @hass_callback
    def _async_save_history(self, event: Event | None = None) -> None:
        """Save the history."""
        self._storage.async_set_advertisement_history(
            self.source,
            DiscoveredDeviceAdvertisementData(
                self.connectable,
                self._expire_seconds,
                self._discovered_device_advertisement_datas,
                self._discovered_device_timestamps,
            ),
        )

    async def async_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic information about the scanner."""
        diag = await super().async_diagnostics()
        diag["storage"] = self._storage.async_get_advertisement_history_as_dict(
            self.source
        )
        return diag
