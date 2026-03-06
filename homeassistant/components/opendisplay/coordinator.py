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

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth advertisement event."""
        if MANUFACTURER_ID not in service_info.manufacturer_data:
            return

        try:
            advertisement = parse_advertisement(
                service_info.manufacturer_data[MANUFACTURER_ID]
            )
        except ValueError:
            _LOGGER.debug(
                "%s: Failed to parse advertisement data", service_info.address
            )
        else:
            self.data = OpenDisplayUpdate(
                address=service_info.address,
                advertisement=advertisement,
            )

        super()._async_handle_bluetooth_event(service_info, change)
