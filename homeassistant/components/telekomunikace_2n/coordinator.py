"""Entity coordinator for the 2N Telekomunikace integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from async_timeout import timeout
from py2n import Py2NDevice
from py2n.exceptions import ApiError, DeviceApiError, Py2NError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERNVAL = timedelta(seconds=30)
_LOGGER = logging.getLogger(__name__)


class Py2NDeviceCoordinator(DataUpdateCoordinator[Py2NDevice]):
    """Class to fetch data from 2N Telekomunikace devices."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, device: Py2NDevice) -> None:
        """Initialize."""
        self.device = device

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERNVAL)

    async def _async_update_data(self) -> Py2NDevice:
        """Update data via library."""
        async with timeout(10):
            try:
                await self.device.update()
            except DeviceApiError as err:
                if (
                    err.error is ApiError.AUTHORIZATION_REQUIRED
                    or ApiError.INSUFFICIENT_PRIVILEGES
                ):
                    self.config_entry.async_start_reauth(self.hass)
            except Py2NError as error:
                raise UpdateFailed(error) from error
            return self.device
