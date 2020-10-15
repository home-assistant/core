"""Support for fetching data from Broadlink devices."""
from abc import ABC, abstractmethod
from datetime import timedelta
from functools import partial
import logging

import broadlink as blk
from broadlink.exceptions import (
    AuthorizationError,
    BroadlinkException,
    CommandNotSupportedError,
    NetworkTimeoutError,
    StorageError,
)

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

_LOGGER = logging.getLogger(__name__)


def get_update_manager(device):
    """Return an update manager for a given Broadlink device."""
    if device.api.model.startswith("RM mini"):
        return BroadlinkRMMini3UpdateManager(device)

    update_managers = {
        "A1": BroadlinkA1UpdateManager,
        "MP1": BroadlinkMP1UpdateManager,
        "RM2": BroadlinkRMUpdateManager,
        "RM4": BroadlinkRMUpdateManager,
        "SP1": BroadlinkSP1UpdateManager,
        "SP2": BroadlinkSP2UpdateManager,
    }
    return update_managers[device.api.type](device)


class BroadlinkUpdateManager(ABC):
    """Representation of a Broadlink update manager.

    Implement this class to manage fetching data from the device and to
    monitor device availability.
    """

    def __init__(self, device):
        """Initialize the update manager."""
        self.device = device
        self.coordinator = DataUpdateCoordinator(
            device.hass,
            _LOGGER,
            name=f"{device.name} ({device.api.model} at {device.api.host[0]})",
            update_method=self.async_update,
            update_interval=timedelta(minutes=1),
        )
        self.available = None
        self.last_update = None

    async def async_update(self):
        """Fetch data from the device and update availability."""
        try:
            data = await self.async_fetch_data()

        except (BroadlinkException, OSError) as err:
            if self.available and (
                dt.utcnow() - self.last_update > timedelta(minutes=3)
                or isinstance(err, (AuthorizationError, OSError))
            ):
                self.available = False
                _LOGGER.warning(
                    "Disconnected from %s (%s at %s)",
                    self.device.name,
                    self.device.api.model,
                    self.device.api.host[0],
                )
            raise UpdateFailed(err) from err

        else:
            if self.available is False:
                _LOGGER.warning(
                    "Connected to %s (%s at %s)",
                    self.device.name,
                    self.device.api.model,
                    self.device.api.host[0],
                )
            self.available = True
            self.last_update = dt.utcnow()
            return data

    @abstractmethod
    async def async_fetch_data(self):
        """Fetch data from the device."""


class BroadlinkA1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink A1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_sensors_raw)


class BroadlinkMP1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink MP1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_power)


class BroadlinkRMMini3UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink RM mini 3 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        hello = partial(
            blk.discover,
            discover_ip_address=self.device.api.host[0],
            timeout=self.device.api.timeout,
        )
        devices = await self.device.hass.async_add_executor_job(hello)
        if not devices:
            raise NetworkTimeoutError("The device is offline")
        return {}


class BroadlinkRMUpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink RM2 and RM4 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_sensors)


class BroadlinkSP1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink SP1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return None


class BroadlinkSP2UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink SP2 devices."""

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
