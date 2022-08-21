"""Integration to integrate MicroBot with Home Assistant."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from microbot import (
    MicroBotApiClient,
    parse_advertisement_data,
)

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

_LOGGER: logging.Logger = logging.getLogger(__package__)
PLATFORMS: list[str] = [Platform.SWITCH]


class MicroBotDataUpdateCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Class to manage fetching data from the MicroBot."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MicroBotApiClient,
        ble_device: BLEDevice,
    ) -> None:
        """Initialize."""
        self.api: MicroBotApiClient = client
        self.data: dict[str, Any] = {}
        self.ble_device = ble_device
        super().__init__(
            hass,
            _LOGGER,
            ble_device.address,
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        super()._async_handle_bluetooth_event(service_info, change)
        if adv := parse_advertisement_data(
            service_info.device, service_info.advertisement
        ):
            _LOGGER.debug("Service_info: %s", service_info)
            _LOGGER.debug("Change: %s", change)
            self.data = adv.data
            _LOGGER.debug("self.data: %s", self.data)
            _LOGGER.debug("%s: MicroBot data: %s", self.ble_device.address, self.data)
            self.api.update_from_advertisement(adv)
