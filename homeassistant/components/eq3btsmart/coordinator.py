"""Coordinator for the eq3btsmart integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from eq3btsmart import Thermostat
from eq3btsmart.exceptions import Eq3Exception
from eq3btsmart.models import DeviceData, Status

from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEVICE_MODEL,
    MANUFACTURER,
    SCAN_INTERVAL,
    SIGNAL_THERMOSTAT_DISCONNECTED,
)

_LOGGER = logging.getLogger(__name__)


class Eq3Coordinator(DataUpdateCoordinator[Status]):
    """Coordinator for the eq3btsmart integration."""

    def __init__(
        self, hass: HomeAssistant, thermostat: Thermostat, mac_address: str
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=format_mac(mac_address),
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            always_update=False,
        )

        self._thermostat = thermostat
        self._mac_address = mac_address
        self._status_future: asyncio.Future[Status] | None = None
        self._device_data_future: asyncio.Future[DeviceData] | None = None

    async def _async_setup(self) -> None:
        """Connect to the thermostat."""

        self._thermostat.register_update_callback(self._async_on_update_received)
        self._thermostat.register_connection_callback(self._async_on_connection_changed)

        await self._async_connect_thermostat()

    async def async_shutdown(self) -> None:
        """Disconnect from the thermostat."""

        self._thermostat.unregister_update_callback(self._async_on_update_received)
        self._thermostat.unregister_connection_callback(
            self._async_on_connection_changed
        )

        await super().async_shutdown()

    async def _async_update_data(self) -> Status:
        """Request status update from thermostat."""

        if not self._thermostat.is_connected:
            await self._async_connect_thermostat()

        self._status_future = self.hass.loop.create_future()

        source_error: Eq3Exception | TimeoutError | None = None
        error: UpdateFailed | None = None

        _LOGGER.debug(
            "[%s] Requesting status update",
            self._mac_address,
        )
        try:
            await self._thermostat.async_get_status()
        except Eq3Exception as e:
            source_error = e
            error = UpdateFailed("Error updating eQ-3 device")
        else:
            try:
                async with asyncio.timeout(SCAN_INTERVAL):
                    status = await self._status_future
            except TimeoutError as e:
                source_error = e
                error = UpdateFailed("Timeout updating eQ-3 device")

        self._status_future.cancel()
        self._status_future = None

        if error is not None:
            async_dispatcher_send(
                self.hass,
                f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{self._mac_address}",
            )
            raise error from source_error

        return status

    async def _async_connect_thermostat(self) -> None:
        """Connect to the thermostat."""

        _LOGGER.debug(
            "[%s] Connecting to eQ-3 device",
            self._mac_address,
        )
        try:
            await self._thermostat.async_connect()

            self._device_data_future = self.hass.loop.create_future()
            await self._thermostat.async_get_status()

            try:
                async with asyncio.timeout(SCAN_INTERVAL):
                    device_data = await self._device_data_future
            except TimeoutError as e:
                self._device_data_future.cancel()
                self._device_data_future = None
                raise UpdateFailed("Timeout connecting to eQ-3 device") from e

            if TYPE_CHECKING:
                assert self.config_entry is not None

            device_registry = dr.async_get(self.hass)
            if device := device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                default_name=format_mac(self._mac_address),
                connections={(CONNECTION_BLUETOOTH, self._mac_address)},
            ):
                sw_version = str(device_data.firmware_version)
                serial_number = device_data.device_serial.value

                if (
                    device.sw_version != sw_version
                    or device.serial_number != serial_number
                ):
                    _LOGGER.debug(
                        "[%s] Updating device registry",
                        self._mac_address,
                    )
                    device_registry.async_update_device(
                        device.id,
                        sw_version=str(device_data.firmware_version),
                        serial_number=device_data.device_serial.value,
                        manufacturer=MANUFACTURER,
                        model=DEVICE_MODEL,
                    )
        except Eq3Exception as e:
            raise UpdateFailed("Error connecting to eQ-3 device") from e

    def _async_on_connection_changed(self, is_connected: bool) -> None:
        """Handle connection changes."""

        if is_connected:
            _LOGGER.debug(
                "[%s] eQ-3 device connected",
                self._mac_address,
            )
        else:
            _LOGGER.error(
                "[%s] eQ-3 device disconnected",
                self._mac_address,
            )
            async_dispatcher_send(
                self.hass,
                f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{self._mac_address}",
            )

    def _async_on_update_received(self) -> None:
        """Handle updated data from the thermostat."""

        _LOGGER.debug(
            "[%s] Received status update: %s",
            self._mac_address,
            self._thermostat.status,
        )

        status = self._thermostat.status
        device_data = self._thermostat.device_data

        if (
            device_data is not None
            and self._device_data_future is not None
            and not self._device_data_future.done()
        ):
            self._device_data_future.set_result(device_data)

        if (
            status is not None
            and self._status_future is not None
            and not self._status_future.done()
        ):
            self._status_future.set_result(status)
        elif status is not None:
            _LOGGER.debug(
                "[%s] Updating coordinator data",
                self._mac_address,
            )
            self.async_set_updated_data(status)
