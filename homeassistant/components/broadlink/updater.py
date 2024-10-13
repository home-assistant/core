"""Support for fetching data from Broadlink devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Generic

import broadlink as blk
from broadlink.exceptions import AuthorizationError, BroadlinkException
from typing_extensions import TypeVar

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from .device import BroadlinkDevice

_ApiT = TypeVar("_ApiT", bound=blk.Device)

_LOGGER = logging.getLogger(__name__)


def get_update_manager(device: BroadlinkDevice[_ApiT]) -> BroadlinkUpdateManager[_ApiT]:
    """Return an update manager for a given Broadlink device."""
    update_managers: dict[str, type[BroadlinkUpdateManager]] = {
        "A1": BroadlinkA1UpdateManager,
        "BG1": BroadlinkBG1UpdateManager,
        "HYS": BroadlinkThermostatUpdateManager,
        "LB1": BroadlinkLB1UpdateManager,
        "LB2": BroadlinkLB1UpdateManager,
        "MP1": BroadlinkMP1UpdateManager,
        "MP1S": BroadlinkMP1SUpdateManager,
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


class BroadlinkUpdateManager(ABC, Generic[_ApiT]):
    """Representation of a Broadlink update manager.

    Implement this class to manage fetching data from the device and to
    monitor device availability.
    """

    SCAN_INTERVAL = timedelta(minutes=1)

    def __init__(self, device: BroadlinkDevice[_ApiT]) -> None:
        """Initialize the update manager."""
        self.device = device
        self.coordinator = DataUpdateCoordinator(
            device.hass,
            _LOGGER,
            name=f"{device.name} ({device.api.model} at {device.api.host[0]})",
            update_method=self.async_update,
            update_interval=self.SCAN_INTERVAL,
        )
        self.available: bool | None = None
        self.last_update: datetime | None = None

    async def async_update(self) -> dict[str, Any] | None:
        """Fetch data from the device and update availability."""
        try:
            data = await self.async_fetch_data()

        except (BroadlinkException, OSError) as err:
            if (
                self.available
                and self.last_update
                and (
                    dt_util.utcnow() - self.last_update > self.SCAN_INTERVAL * 3
                    or isinstance(err, (AuthorizationError, OSError))
                )
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
    async def async_fetch_data(self) -> dict[str, Any] | None:
        """Fetch data from the device."""


class BroadlinkA1UpdateManager(BroadlinkUpdateManager[blk.a1]):
    """Manages updates for Broadlink A1 devices."""

    SCAN_INTERVAL = timedelta(seconds=10)

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_sensors_raw)


class BroadlinkMP1UpdateManager(BroadlinkUpdateManager[blk.mp1]):
    """Manages updates for Broadlink MP1 devices."""

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.check_power)


class BroadlinkMP1SUpdateManager(BroadlinkUpdateManager[blk.mp1s]):
    """Manages updates for Broadlink MP1 devices."""

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        power = await self.device.async_request(self.device.api.check_power)
        sensors = await self.device.async_request(self.device.api.get_state)
        return {**power, **sensors}


class BroadlinkRMUpdateManager(BroadlinkUpdateManager[blk.rm]):
    """Manages updates for Broadlink remotes."""

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        device = self.device

        if hasattr(device.api, "check_sensors"):
            data = await device.async_request(device.api.check_sensors)
            return self.normalize(data, self.coordinator.data)

        await device.async_request(device.api.update)
        return {}

    @staticmethod
    def normalize(
        data: dict[str, Any], previous_data: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Fix firmware issue.

        See https://github.com/home-assistant/core/issues/42100.
        """
        if data["temperature"] == -7:
            if previous_data is None or previous_data["temperature"] is None:
                data["temperature"] = None
            elif abs(previous_data["temperature"] - data["temperature"]) > 3:
                data["temperature"] = previous_data["temperature"]
        return data


class BroadlinkSP1UpdateManager(BroadlinkUpdateManager[blk.sp1]):
    """Manages updates for Broadlink SP1 devices."""

    async def async_fetch_data(self) -> dict[str, Any] | None:
        """Fetch data from the device."""
        return None


class BroadlinkSP2UpdateManager(BroadlinkUpdateManager[blk.sp2]):
    """Manages updates for Broadlink SP2 devices."""

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        device = self.device

        data = {}
        data["pwr"] = await device.async_request(device.api.check_power)

        if hasattr(device.api, "get_energy"):
            data["power"] = await device.async_request(device.api.get_energy)

        return data


class BroadlinkBG1UpdateManager(BroadlinkUpdateManager[blk.bg1]):
    """Manages updates for Broadlink BG1 devices."""

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.get_state)


class BroadlinkSP4UpdateManager(BroadlinkUpdateManager[blk.sp4]):
    """Manages updates for Broadlink SP4 devices."""

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.get_state)


class BroadlinkLB1UpdateManager(BroadlinkUpdateManager[blk.lb1]):
    """Manages updates for Broadlink LB1 devices."""

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.get_state)


class BroadlinkThermostatUpdateManager(BroadlinkUpdateManager[blk.hysen]):
    """Manages updates for thermostats with Broadlink DNA."""

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        return await self.device.async_request(self.device.api.get_full_status)
