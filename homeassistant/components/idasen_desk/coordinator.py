"""Coordinator for the IKEA Idasen Desk integration."""

from __future__ import annotations

import logging

from idasen_ha import Desk

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
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

        self.desk = Desk(self.async_set_updated_data)

    async def async_connect(self) -> bool:
        """Connect to desk."""
        _LOGGER.debug("Trying to connect %s", self._address)
        self._expected_connected = True
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if ble_device is None:
            _LOGGER.debug("No BLEDevice for %s", self._address)
            return False
        await self.desk.connect(ble_device)
        return True

    async def async_disconnect(self) -> None:
        """Disconnect from desk."""
        self._expected_connected = False
        _LOGGER.debug("Disconnecting from %s", self._address)
        await self.desk.disconnect()

    async def async_connect_if_expected(self) -> None:
        """Ensure that the desk is connected if that is the expected state."""
        if self._expected_connected:
            await self.async_connect()
