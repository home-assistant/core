"""Coordinator for the IKEA Idasen Desk integration."""

from __future__ import annotations

import logging

from idasen_ha import Desk

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type IdasenDeskConfigEntry = ConfigEntry[IdasenDeskCoordinator]


class IdasenDeskCoordinator(DataUpdateCoordinator[int | None]):
    """Class to manage updates for the Idasen Desk."""

    config_entry: IdasenDeskConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: IdasenDeskConfigEntry,
        address: str,
    ) -> None:
        """Init IdasenDeskCoordinator."""

        super().__init__(
            hass, _LOGGER, config_entry=config_entry, name=config_entry.title
        )
        self.address = address
        self._expected_connected = False

        self.desk = Desk(self.async_set_updated_data)

    async def async_connect(self) -> bool:
        """Connect to desk."""
        _LOGGER.debug("Trying to connect %s", self.address)
        self._expected_connected = True
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            _LOGGER.debug("No BLEDevice for %s", self.address)
            return False
        await self.desk.connect(ble_device)
        return True

    async def async_disconnect(self) -> None:
        """Disconnect from desk."""
        self._expected_connected = False
        _LOGGER.debug("Disconnecting from %s", self.address)
        await self.desk.disconnect()

    async def async_connect_if_expected(self) -> None:
        """Ensure that the desk is connected if that is the expected state."""
        if self._expected_connected:
            await self.async_connect()
