"""Support for fetching data from Broadlink devices."""
from abc import ABC, abstractmethod
from datetime import timedelta
import logging

from broadlink.exceptions import (
    AuthorizationError,
    BroadlinkException,
    CommandNotSupportedError,
    ConnectionClosedError,
    DeviceOfflineError,
    StorageError,
)

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


def get_update_coordinator(device):
    """Return an update coordinator for a given Broadlink device."""
    updaters = {
        "A1": A1DataUpdater,
        "MP1": MP1DataUpdater,
        "RM2": RMDataUpdater,
        "RM4": RMDataUpdater,
        "SP1": SP1DataUpdater,
        "SP2": SP2DataUpdater,
    }
    return updaters[device.api.type](device).coordinator


class BroadlinkDataUpdater(ABC):
    """Representation of a Broadlink data updater."""

    def __init__(self, device):
        """Initialize the data updater."""
        self.device = device
        self.coordinator = DataUpdateCoordinator(
            device.hass,
            _LOGGER,
            name="device",
            update_method=self.async_update,
            update_interval=timedelta(seconds=60),
        )

    async def async_update(self):
        """Fetch data from the device."""
        try:
            data = await self.async_fetch_data()

        except (AuthorizationError, ConnectionClosedError, DeviceOfflineError) as err:
            if self.coordinator.last_update_success:
                _LOGGER.warning(
                    "Disconnected from the device at %s", self.device.api.host[0]
                )
            raise UpdateFailed(err)

        except BroadlinkException as err:
            raise UpdateFailed(err)

        else:
            if not self.coordinator.last_update_success:
                _LOGGER.warning(
                    "Connected to the device at %s", self.device.api.host[0]
                )
            return data

    @abstractmethod
    async def async_fetch_data(self):
        """Fetch data from the device."""


class A1DataUpdater(BroadlinkDataUpdater):
    """Data updater for Broadlink A1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_sensors_raw)


class MP1DataUpdater(BroadlinkDataUpdater):
    """Data updater for Broadlink MP1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_power)


class RMDataUpdater(BroadlinkDataUpdater):
    """Data updater for Broadlink RM2 and RM4 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_sensors)


class SP1DataUpdater(BroadlinkDataUpdater):
    """Data updater for Broadlink SP1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return None


class SP2DataUpdater(BroadlinkDataUpdater):
    """Data updater for Broadlink SP2 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        data = {}
        data["state"] = await self.device.async_request(self.device.api.check_power)
        try:
            data["load_power"] = await self.device.async_request(
                self.device.api.get_energy
            )
        except (CommandNotSupportedError, StorageError):
            data["load_power"] = None
        return data
