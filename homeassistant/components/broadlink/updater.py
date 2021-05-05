"""Support for fetching data from Broadlink devices."""
from abc import ABC, abstractmethod
from datetime import timedelta
import logging

from broadlink.exceptions import AuthorizationError, BroadlinkException

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

_LOGGER = logging.getLogger(__name__)


def get_update_manager(device):
    """Return an update manager for a given Broadlink device."""
    update_managers = {
        "A1": BroadlinkA1UpdateManager,
        "BG1": BroadlinkBG1UpdateManager,
        "MP1": BroadlinkMP1UpdateManager,
        "RM4MINI": BroadlinkRMUpdateManager,
        "RM4PRO": BroadlinkRMUpdateManager,
        "RMMINI": BroadlinkRMUpdateManager,
        "RMMINIB": BroadlinkRMUpdateManager,
        "RMPRO": BroadlinkRMUpdateManager,
        "SP1": BroadlinkSP1UpdateManager,
        "SP2": BroadlinkSP2UpdateManager,
        "SP2S": BroadlinkSP2UpdateManager,
        "SP3": BroadlinkSP2UpdateManager,
        "SP3S": BroadlinkSP2UpdateManager,
        "SP4": BroadlinkSP4UpdateManager,
        "SP4B": BroadlinkSP4UpdateManager,
    }
    return update_managers[device.api.type](device)


class BroadlinkUpdateManager(ABC):
    """Representation of a Broadlink update manager.

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

        except (BroadlinkException, ValueError, OSError) as err:
            if self.available and (
                dt.utcnow() - self.last_update > self.SCAN_INTERVAL * 3
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

    SCAN_INTERVAL = timedelta(seconds=10)

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_sensors_raw)


class BroadlinkMP1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink MP1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_power)


class BroadlinkRMUpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink remotes."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        device = self.device

        if hasattr(device.api, "check_sensors"):
            data = await device.async_request(device.api.check_sensors)

            # Firmware issue. See https://github.com/home-assistant/core/issues/42100.
            if data["temperature"] == -7:
                if self.coordinator.data is not None:
                    return self.coordinator.data
                raise ValueError("The device returned malformed data")

            return data

        await device.async_request(device.api.update)
        return {}


class BroadlinkSP1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink SP1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return None


class BroadlinkSP2UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink SP2 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        device = self.device

        data = {}
        data["pwr"] = await device.async_request(device.api.check_power)

        if hasattr(device.api, "get_energy"):
            data["power"] = await device.async_request(device.api.get_energy)

        return data


class BroadlinkBG1UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink BG1 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.get_state)


class BroadlinkSP4UpdateManager(BroadlinkUpdateManager):
    """Manages updates for Broadlink SP4 devices."""

    async def async_fetch_data(self):
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.get_state)
