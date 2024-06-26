"""Coordinator for Iskra integration."""

from datetime import timedelta
import logging

from pyiskra.devices import Device
from pyiskra.exceptions import (
    DeviceConnectionError,
    DeviceTimeoutError,
    InvalidResponseCode,
    NotAuthorised,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IskraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Iskra data."""

    def __init__(self, hass: HomeAssistant, device: Device) -> None:
        """Initialize."""
        self._device = device
        self.name = device.serial
        self._is_available = False

        update_interval = timedelta(seconds=60)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def device(self):
        """Return the device."""
        return self._device

    async def _async_update_data(self):
        """Fetch data from Iskra device."""
        try:
            await self.device.update_status()
            _LOGGER.info("Data updated for device %s", self.device.serial)
            self._is_available = True
        except DeviceTimeoutError:
            self._is_available = False
            _LOGGER.error("Timeout error for device %s", self.device.serial)
        except DeviceConnectionError:
            self._is_available = False
            _LOGGER.error("Could not fetch data from device %s", self.device.serial)
        except NotAuthorised:
            self._is_available = False
            _LOGGER.error(
                "Not authorised to fetch data from device %s", self.device.serial
            )
        except InvalidResponseCode:
            self._is_available = False
            _LOGGER.error("Invalid response code from device %s", self.device.serial)
