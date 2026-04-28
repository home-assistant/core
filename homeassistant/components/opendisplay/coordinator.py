"""Passive BLE coordinator for OpenDisplay devices."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging

from opendisplay import MANUFACTURER_ID, AdvertisementTracker, parse_advertisement
from opendisplay.models.advertisement import AdvertisementData, ButtonChangeEvent

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
    button_events: list[ButtonChangeEvent] = field(default_factory=list)


class OpenDisplayCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Coordinator for passive BLE advertisement updates from an OpenDisplay device."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            address,
            BluetoothScanningMode.PASSIVE,
            connectable=True,
        )
        self.data: OpenDisplayUpdate | None = None
        self._tracker: AdvertisementTracker = AdvertisementTracker()

    @callback
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Handle the device going unavailable."""
        if self._available:
            _LOGGER.info("%s: Device is unavailable", service_info.address)
        super()._async_handle_unavailable(service_info)

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth advertisement event."""
        if not self._available:
            _LOGGER.info("%s: Device is available again", service_info.address)

        if MANUFACTURER_ID not in service_info.manufacturer_data:
            super()._async_handle_bluetooth_event(service_info, change)
            return

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
            button_events = self._tracker.update(service_info.address, advertisement)
            self.data = OpenDisplayUpdate(
                address=service_info.address,
                advertisement=advertisement,
                button_events=button_events,
            )

        super()._async_handle_bluetooth_event(service_info, change)
