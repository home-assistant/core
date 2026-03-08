"""Passive BLE coordinator for OpenDisplay devices."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from opendisplay import MANUFACTURER_ID, parse_advertisement
from opendisplay.models.advertisement import AdvertisementData

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass
class OpenDisplayUpdate:
    """Parsed advertisement data for one OpenDisplay device."""

    address: str
    advertisement: AdvertisementData


class OpenDisplayCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Coordinator for passive BLE advertisement updates from an OpenDisplay device."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            address,
            BluetoothScanningMode.PASSIVE,
        )
        self.data: OpenDisplayUpdate | None = None
        self._was_unavailable = False

    @callback
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Handle the device going unavailable."""
        if self._was_unavailable:
            return
        self._was_unavailable = True
        _LOGGER.info("%s: Device is unavailable", service_info.address)
        super()._async_handle_unavailable(service_info)

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth advertisement event."""
        if MANUFACTURER_ID not in service_info.manufacturer_data:
            super()._async_handle_bluetooth_event(service_info, change)
            return

        if self._was_unavailable:
            self._was_unavailable = False
            _LOGGER.info("%s: Device is available again", service_info.address)

        try:
            advertisement = parse_advertisement(
                service_info.manufacturer_data[MANUFACTURER_ID]
            )
        except ValueError as err:
            _LOGGER.debug(
                "%s: Failed to parse advertisement data: %s",
                service_info.address,
                err,
                exc_info=True,
            )
        else:
            self.data = OpenDisplayUpdate(
                address=service_info.address,
                advertisement=advertisement,
            )

        super()._async_handle_bluetooth_event(service_info, change)
