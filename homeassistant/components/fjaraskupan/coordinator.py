"""The Fjäråskupan data update coordinator."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
import logging

from fjaraskupan import Device, State

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_address_present,
    async_ble_device_from_address,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class UnableToConnect(HomeAssistantError):
    """Exception to indicate that we cannot connect to device."""


class FjaraskupanCoordinator(DataUpdateCoordinator[State]):
    """Update coordinator for each device."""

    def __init__(
        self, hass: HomeAssistant, device: Device, device_info: DeviceInfo
    ) -> None:
        """Initialize the coordinator."""
        self.device = device
        self.device_info = device_info
        self._refresh_was_scheduled = False

        super().__init__(
            hass, _LOGGER, name="Fjäråskupan", update_interval=timedelta(seconds=120)
        )

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        self._refresh_was_scheduled = scheduled
        await super()._async_refresh(
            log_failures=log_failures,
            raise_on_auth_failed=raise_on_auth_failed,
            scheduled=scheduled,
            raise_on_entry_error=raise_on_entry_error,
        )

    async def _async_update_data(self) -> State:
        """Handle an explicit update request."""
        if self._refresh_was_scheduled:
            if async_address_present(self.hass, self.device.address, False):
                return self.device.state
            raise UpdateFailed(
                "No data received within schedule, and device is no longer present"
            )

        if (
            ble_device := async_ble_device_from_address(
                self.hass, self.device.address, True
            )
        ) is None:
            raise UpdateFailed("No connectable path to device")
        async with self.device.connect(ble_device) as device:
            await device.update()
        return self.device.state

    def detection_callback(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Handle a new announcement of data."""
        self.device.detection_callback(service_info.device, service_info.advertisement)
        self.async_set_updated_data(self.device.state)

    @asynccontextmanager
    async def async_connect_and_update(self) -> AsyncIterator[Device]:
        """Provide an up-to-date device for use during connections."""
        if (
            ble_device := async_ble_device_from_address(
                self.hass, self.device.address, True
            )
        ) is None:
            raise UnableToConnect("No connectable path to device")

        async with self.device.connect(ble_device) as device:
            yield device

        self.async_set_updated_data(self.device.state)
