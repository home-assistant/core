"""DataUpdateCoordinators for the System monitor integration."""
from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
import logging
import os
from typing import NamedTuple, TypeVar

import psutil
from psutil._common import sdiskusage, shwtemp, snetio, snicaddr, sswap

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class VirtualMemory(NamedTuple):
    """Represents virtual memory.

    psutil defines virtual memory by platform.
    Create our own definition here to be platform independent.
    """

    total: float
    available: float
    percent: float
    used: float
    free: float


dataT = TypeVar(
    "dataT",
    bound=datetime
    | dict[str, list[shwtemp]]
    | dict[str, list[snicaddr]]
    | dict[str, snetio]
    | float
    | list[psutil.Process]
    | sswap
    | VirtualMemory
    | tuple[float, float, float]
    | sdiskusage,
)


class MonitorCoordinator(DataUpdateCoordinator[dataT]):
    """A System monitor Base Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, name: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"System Monitor {name}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )

    async def _async_update_data(self) -> dataT:
        """Fetch data."""
        return await self.hass.async_add_executor_job(self.update_data)

    @abstractmethod
    def update_data(self) -> dataT:
        """To be extended by data update coordinators."""


class SystemMonitorDiskCoordinator(MonitorCoordinator[sdiskusage]):
    """A System monitor Disk Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, name: str, argument: str) -> None:
        """Initialize the disk coordinator."""
        super().__init__(hass, name)
        self._argument = argument

    def update_data(self) -> sdiskusage:
        """Fetch data."""
        try:
            return psutil.disk_usage(self._argument)
        except PermissionError as err:
            raise UpdateFailed(f"No permission to access {self._argument}") from err
        except OSError as err:
            raise UpdateFailed(f"OS error for {self._argument}") from err


class SystemMonitorSwapCoordinator(MonitorCoordinator[sswap]):
    """A System monitor Swap Data Update Coordinator."""

    def update_data(self) -> sswap:
        """Fetch data."""
        return psutil.swap_memory()


class SystemMonitorMemoryCoordinator(MonitorCoordinator[VirtualMemory]):
    """A System monitor Memory Data Update Coordinator."""

    def update_data(self) -> VirtualMemory:
        """Fetch data."""
        memory = psutil.virtual_memory()
        return VirtualMemory(
            memory.total, memory.available, memory.percent, memory.used, memory.free
        )


class SystemMonitorNetIOCoordinator(MonitorCoordinator[dict[str, snetio]]):
    """A System monitor Network IO Data Update Coordinator."""

    def update_data(self) -> dict[str, snetio]:
        """Fetch data."""
        return psutil.net_io_counters(pernic=True)


class SystemMonitorNetAddrCoordinator(MonitorCoordinator[dict[str, list[snicaddr]]]):
    """A System monitor Network Address Data Update Coordinator."""

    def update_data(self) -> dict[str, list[snicaddr]]:
        """Fetch data."""
        return psutil.net_if_addrs()


class SystemMonitorLoadCoordinator(MonitorCoordinator[tuple[float, float, float]]):
    """A System monitor Load Data Update Coordinator."""

    def update_data(self) -> tuple[float, float, float]:
        """Fetch data."""
        return os.getloadavg()


class SystemMonitorProcessorCoordinator(MonitorCoordinator[float]):
    """A System monitor Processor Data Update Coordinator."""

    def update_data(self) -> float:
        """Fetch data."""
        return psutil.cpu_percent(interval=None)


class SystemMonitorBootTimeCoordinator(MonitorCoordinator[datetime]):
    """A System monitor Processor Data Update Coordinator."""

    def update_data(self) -> datetime:
        """Fetch data."""
        return dt_util.utc_from_timestamp(psutil.boot_time())


class SystemMonitorProcessCoordinator(MonitorCoordinator[list[psutil.Process]]):
    """A System monitor Process Data Update Coordinator."""

    def update_data(self) -> list[psutil.Process]:
        """Fetch data."""
        processes = psutil.process_iter()
        return list(processes)


class SystemMonitorCPUtempCoordinator(MonitorCoordinator[dict[str, list[shwtemp]]]):
    """A System monitor CPU Temperature Data Update Coordinator."""

    def update_data(self) -> dict[str, list[shwtemp]]:
        """Fetch data."""
        try:
            return psutil.sensors_temperatures()
        except AttributeError as err:
            raise UpdateFailed("OS does not provide temperature sensors") from err
