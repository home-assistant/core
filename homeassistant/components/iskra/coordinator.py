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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IskraDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Iskra data."""

    def __init__(self, hass: HomeAssistant, device: Device) -> None:
        """Initialize."""
        self.device = device

        update_interval = timedelta(seconds=60)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from Iskra device."""
        try:
            await self.device.update_status()
        except DeviceTimeoutError as e:
            raise UpdateFailed(
                f"Timeout error occurred while updating data for device {self.device.serial}"
            ) from e
        except DeviceConnectionError as e:
            raise UpdateFailed(
                f"Connection error occurred while updating data for device {self.device.serial}"
            ) from e
        except NotAuthorised as e:
            raise UpdateFailed(
                f"Not authorised to fetch data from device {self.device.serial}"
            ) from e
        except InvalidResponseCode as e:
            raise UpdateFailed(
                f"Invalid response code from device {self.device.serial}"
            ) from e
