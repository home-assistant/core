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

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type IskraConfigEntry = ConfigEntry[list[IskraDataUpdateCoordinator]]


class IskraDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Iskra data."""

    config_entry: IskraConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: IskraConfigEntry, device: Device
    ) -> None:
        """Initialize."""
        self.device = device

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
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
