"""Coordinator for the IKEA Idasen Desk integration."""

from __future__ import annotations

import logging

from idasen_ha import Desk

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type IdasenDeskConfigEntry = ConfigEntry[IdasenDeskCoordinator]

UPDATE_DEBOUNCE_TIME = 0.2


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
        self.desk = Desk(self._async_handle_update)

        self._expected_connected = False
        self._height: int | None = None

        self._debouncer = Debouncer(
            hass=self.hass,
            logger=_LOGGER,
            cooldown=UPDATE_DEBOUNCE_TIME,
            immediate=True,
            function=callback(lambda: self.async_set_updated_data(self._height)),
        )

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

    @callback
    def _async_handle_update(self, height: int | None) -> None:
        """Handle an update from the desk."""
        self._height = height
        self._debouncer.async_schedule_call()
