"""Coordinator for the IKEA Idasen Desk integration."""

from __future__ import annotations

import asyncio
import logging

from idasen_ha import Desk

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class IdasenDeskCoordinator(DataUpdateCoordinator[int | None]):
    """Class to manage updates for the Idasen Desk."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        address: str,
    ) -> None:
        """Init IdasenDeskCoordinator."""

        super().__init__(hass, logger, name=name)
        self._address = address
        self._expected_connected = False
        self._connection_lost = False
        self._disconnect_lock = asyncio.Lock()

        self.desk = Desk(self.async_set_updated_data)

    async def async_connect(self) -> bool:
        """Connect to desk."""
        _LOGGER.debug("Trying to connect %s", self._address)
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if ble_device is None:
            _LOGGER.debug("No BLEDevice for %s", self._address)
            return False
        self._expected_connected = True
        await self.desk.connect(ble_device)
        return True

    async def async_disconnect(self) -> None:
        """Disconnect from desk."""
        _LOGGER.debug("Disconnecting from %s", self._address)
        self._expected_connected = False
        self._connection_lost = False
        await self.desk.disconnect()

    async def async_ensure_connection_state(self) -> None:
        """Check if the expected connection state matches the current state.

        If the expected and current state don't match, calls connect/disconnect
        as needed.
        """
        if self._expected_connected:
            if not self.desk.is_connected:
                _LOGGER.debug("Desk disconnected. Reconnecting")
                self._connection_lost = True
                await self.async_connect()
            elif self._connection_lost:
                _LOGGER.info("Reconnected to desk")
                self._connection_lost = False
        elif self.desk.is_connected:
            if self._disconnect_lock.locked():
                _LOGGER.debug("Already disconnecting")
                return
            async with self._disconnect_lock:
                _LOGGER.debug("Desk is connected but should not be. Disconnecting")
                await self.desk.disconnect()

    @callback
    def async_set_updated_data(self, data: int | None) -> None:
        """Handle data update."""
        self.hass.async_create_task(self.async_ensure_connection_state())
        return super().async_set_updated_data(data)
