"""Coordinator for the eq3btsmart integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from eq3btsmart import Thermostat
from eq3btsmart.exceptions import Eq3Exception
from eq3btsmart.models import DeviceData, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEVICE_MODEL,
    MANUFACTURER,
    RECONNECT_INTERVAL,
    SCAN_INTERVAL,
    SIGNAL_THERMOSTAT_DISCONNECTED,
)

_LOGGER = logging.getLogger(__name__)

type Eq3ConfigEntry = ConfigEntry[Eq3ConfigEntryData]


@dataclass(slots=True)
class Eq3ConfigEntryData:
    """Config entry for a single eQ-3 device."""

    thermostat: Thermostat
    coordinator: Eq3Coordinator


class Eq3Coordinator(DataUpdateCoordinator[Status]):
    """Coordinator for the eq3btsmart integration."""

    config_entry: Eq3ConfigEntry
    _status_future: asyncio.Future[Status | None] | None
    _device_data_future: asyncio.Future[DeviceData | None] | None
    _mac_address: str
    _schedule_reconnect: bool = False

    def __init__(
        self, hass: HomeAssistant, entry: Eq3ConfigEntry, mac_address: str
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=format_mac(mac_address),
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            config_entry=entry,
            always_update=False,
        )

        self._mac_address = mac_address
        self._status_future = None
        self._device_data_future = None

    async def _async_setup(self) -> None:
        """Connect to the thermostat."""

        self.config_entry.runtime_data.thermostat.register_update_callback(
            self._async_on_update_received
        )
        self.config_entry.runtime_data.thermostat.register_connection_callback(
            self._async_on_connection_changed
        )

        await self._async_connect_thermostat()

    async def async_shutdown(self) -> None:
        """Disconnect from the thermostat."""

        self.config_entry.runtime_data.thermostat.unregister_update_callback(
            self._async_on_update_received
        )
        self.config_entry.runtime_data.thermostat.unregister_connection_callback(
            self._async_on_connection_changed
        )

        await super().async_shutdown()

    async def _async_update_data(self) -> Status:
        """Request status update from thermostat."""

        if self._schedule_reconnect:
            self._schedule_reconnect = False
            await self._async_connect_thermostat()

        self._status_future = self.hass.loop.create_future()

        eq3_error: Eq3Exception | None = None
        error: UpdateFailed | None = None
        status: Status | None = None

        _LOGGER.debug(
            "[%s] Requesting status update",
            self._mac_address,
        )
        try:
            await self.config_entry.runtime_data.thermostat.async_get_status()
        except Eq3Exception as e:
            eq3_error = e
            error = UpdateFailed(f"Error updating eQ-3 device: {e}")
        else:
            status = await self._status_future

        self._status_future = None

        if error is not None:
            raise error from eq3_error

        if status is None:
            raise UpdateFailed("No status received")

        return status

    async def _async_connect_thermostat(self) -> None:
        """Connect the thermostat."""

        while True:
            _LOGGER.debug(
                "[%s] Connecting to eQ-3 device",
                self._mac_address,
            )
            try:
                await self.config_entry.runtime_data.thermostat.async_connect()

                self._device_data_future = self.hass.loop.create_future()
                await self.config_entry.runtime_data.thermostat.async_get_status()

                async with asyncio.timeout(RECONNECT_INTERVAL):
                    device_data = await self._device_data_future

                if device_data is None:
                    raise UpdateFailed("No device data received")

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
            except Eq3Exception:
                _LOGGER.debug(
                    "[%s] Connection to eQ-3 device failed, retrying in %s seconds",
                    self._mac_address,
                    RECONNECT_INTERVAL,
                )
                await asyncio.sleep(RECONNECT_INTERVAL)
                continue

            return

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
            self._schedule_reconnect = True

    def _async_on_update_received(self) -> None:
        """Handle updated data from the thermostat."""

        _LOGGER.debug(
            "[%s] Received status update: %s",
            self._mac_address,
            self.config_entry.runtime_data.thermostat.status,
        )

        if self.config_entry.runtime_data.thermostat.device_data is not None:
            if (
                self._device_data_future is not None
                and not self._device_data_future.done()
            ):
                self._device_data_future.set_result(
                    self.config_entry.runtime_data.thermostat.device_data
                )

        if self._status_future is not None and not self._status_future.done():
            self._status_future.set_result(
                self.config_entry.runtime_data.thermostat.status
            )
        elif self.config_entry.runtime_data.thermostat.status is not None:
            _LOGGER.debug(
                "[%s] Updating coordinator data",
                self._mac_address,
            )
            self.async_set_updated_data(
                self.config_entry.runtime_data.thermostat.status
            )
