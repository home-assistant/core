"""Coordinator for the eq3btsmart integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from eq3btsmart import (
    Eq3Event,
    Eq3StateException,
    Eq3TimeoutException,
    Schedule,
    Thermostat,
)
from eq3btsmart.exceptions import Eq3Exception
from eq3btsmart.models import DeviceData, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEVICE_MODEL, MANUFACTURER, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class Eq3Coordinator(DataUpdateCoordinator[Status]):
    """Coordinator for the eq3btsmart integration."""

    config_entry: ConfigEntry
    _mac_address: str
    _thermostat: Thermostat

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        mac_address: str,
        thermostat: Thermostat,
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
        self._thermostat = thermostat

    async def _async_setup(self) -> None:
        """Connect to the thermostat."""
        self._thermostat.register_callback(Eq3Event.CONNECTED, self._async_on_connected)
        self._thermostat.register_callback(
            Eq3Event.DISCONNECTED, self._async_on_disconnected
        )
        self._thermostat.register_callback(
            Eq3Event.STATUS_RECEIVED, self._async_on_status_received
        )

        await self._async_connect_thermostat()

    async def async_shutdown(self) -> None:
        """Disconnect from the thermostat."""
        _LOGGER.debug(
            "[%s] Shutting down coordinator",
            self._mac_address,
        )
        self._thermostat.unregister_callback(
            Eq3Event.CONNECTED, self._async_on_connected
        )
        self._thermostat.unregister_callback(
            Eq3Event.DISCONNECTED, self._async_on_disconnected
        )
        self._thermostat.unregister_callback(
            Eq3Event.STATUS_RECEIVED, self._async_on_status_received
        )

        await super().async_shutdown()

    async def _async_update_data(self) -> Status:
        """Request status update from thermostat."""
        _LOGGER.debug(
            "[%s] Requesting status update",
            self._mac_address,
        )
        self._thermostat.unregister_callback(
            Eq3Event.STATUS_RECEIVED, self._async_on_status_received
        )
        try:
            status = await self._thermostat.async_get_status()
        except Eq3Exception as ex:
            raise UpdateFailed(f"Error updating eQ-3 device: {ex}") from ex
        finally:
            self._thermostat.register_callback(
                Eq3Event.STATUS_RECEIVED, self._async_on_status_received
            )

        return status

    async def _async_on_status_received(self, status: Status) -> None:
        """Handle status received event."""
        self.async_set_updated_data(status)

    async def _async_connect_thermostat(self) -> None:
        """Connect the thermostat."""
        while True:
            _LOGGER.debug(
                "[%s] Connecting to eQ-3 device",
                self._mac_address,
            )
            try:
                await self._thermostat.async_connect()
            except Eq3TimeoutException:
                # Thermostat might be in a bugged state, we need to set a temperature to fix it.
                await self._thermostat.async_disconnect()
                await self._thermostat.async_connect(
                    bugged_state_fix_value=self.data.target_temperature
                    if self.data
                    else 20.0
                )
            except Eq3StateException:
                pass
            except Eq3Exception as ex:
                _LOGGER.debug(
                    "[%s] Connection to eQ-3 device failed, retrying in %s seconds: %s",
                    self._mac_address,
                    SCAN_INTERVAL,
                    ex,
                )
                await asyncio.sleep(SCAN_INTERVAL)
                continue

            _LOGGER.debug(
                "[%s] Connected to eQ-3 device",
                self._mac_address,
            )
            return

    def _async_on_connected(
        self,
        device_data: DeviceData,
        status: Status,
        schedule: Schedule,
    ) -> None:
        """Handle connected event."""
        device_registry = dr.async_get(self.hass)
        if not (
            device := device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                default_name=format_mac(self._mac_address),
                connections={(CONNECTION_BLUETOOTH, self._mac_address)},
            )
        ):
            _LOGGER.error(
                "[%s] Failed to create device registry entry",
                self._mac_address,
            )
            return

        sw_version = str(device_data.firmware_version)
        serial_number = device_data.device_serial

        if device.sw_version != sw_version or device.serial_number != serial_number:
            _LOGGER.debug(
                "[%s] Updating device registry",
                self._mac_address,
            )
            device_registry.async_update_device(
                device.id,
                sw_version=sw_version,
                serial_number=serial_number,
                manufacturer=MANUFACTURER,
                model=DEVICE_MODEL,
            )

    def _async_on_disconnected(self) -> None:
        """Handle disconnected event."""
        _LOGGER.debug(
            "[%s] eQ-3 device disconnected",
            self._mac_address,
        )
