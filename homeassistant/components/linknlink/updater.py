"""Support for fetching data from LinknLink devices."""
from abc import ABC, abstractmethod
from datetime import timedelta
import logging

from linknlink.exceptions import AuthorizationError, LinknLinkException

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


def get_update_manager(device):
    """Return an update manager for a given LinknLink device."""
    update_managers = {
        "EHUB": LinknLinkEHUBUpdateManager,
        "ETHS": LinknLinkEHUBUpdateManager,
        "MOTION": LinknLinkEHUBUpdateManager,
    }
    return update_managers[device.api.type](device)


class LinknLinkUpdateManager(ABC):
    """Representation of a linknlink update manager.

    Implement this class to manage fetching data from the device and to
    monitor device availability.
    """

    SCAN_INTERVAL = timedelta(minutes=1)

    def __init__(self, device):
        """Initialize the update manager."""
        self.device = device
        self.coordinator = DataUpdateCoordinator(
            device.hass,
            _LOGGER,
            name=f"{device.name} ({device.api.model} at {device.api.host[0]})",
            update_method=self.async_update,
            update_interval=self.SCAN_INTERVAL,
        )
        self.available = None
        self.last_update = None

    async def async_update(self):
        """Fetch data from the device and update availability."""
        try:
            data = await self.async_fetch_data()

        except (LinknLinkException, OSError) as err:
            if self.available and (
                dt_util.utcnow() - self.last_update > self.SCAN_INTERVAL * 3
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

        if self.available is False:
            _LOGGER.warning(
                "Connected to %s (%s at %s)",
                self.device.name,
                self.device.api.model,
                self.device.api.host[0],
            )
        self.available = True
        self.last_update = dt_util.utcnow()
        return data

    @abstractmethod
    async def async_fetch_data(self):
        """Fetch data from the device."""


class LinknLinkEHUBUpdateManager(LinknLinkUpdateManager):
    """Manages updates for linknlink remotes."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        device = self.device
        if hasattr(device.api, "check_sensors"):
            data = await device.async_request(device.api.check_sensors)
            return data

        await device.async_request(device.api.update)
        return {}
