"""DataUpdateCoordinators for the System monitor integration."""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
import logging
import os
from typing import NamedTuple, TypeVar

from psutil import Process
from psutil._common import sdiskusage, shwtemp, snetio, snicaddr, sswap
import psutil_home_assistant as ha_psutil

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
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
    | list[Process]
    | sswap
    | VirtualMemory
    | tuple[float, float, float]
    | sdiskusage
    | None,
)


class MonitorCoordinator(TimestampDataUpdateCoordinator[dataT]):
    """A System monitor Base Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, psutil_wrapper: ha_psutil.PsutilWrapper, name: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"System Monitor {name}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )
        self._psutil = psutil_wrapper.psutil

    async def _async_update_data(self) -> dataT:
        """Fetch data."""
        return await self.hass.async_add_executor_job(self.update_data)

    @abstractmethod
    def update_data(self) -> dataT:
        """To be extended by data update coordinators."""


class SystemMonitorDiskCoordinator(MonitorCoordinator[sdiskusage]):
    """A System monitor Disk Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        psutil_wrapper: ha_psutil.PsutilWrapper,
        name: str,
        argument: str,
    ) -> None:
        """Initialize the disk coordinator."""
        super().__init__(hass, psutil_wrapper, name)
        self._argument = argument

    def update_data(self) -> sdiskusage:
        """Fetch data."""
        try:
            usage: sdiskusage = self._psutil.disk_usage(self._argument)
            _LOGGER.debug("sdiskusage: %s", usage)
            return usage
        except PermissionError as err:
            raise UpdateFailed(f"No permission to access {self._argument}") from err
        except OSError as err:
            raise UpdateFailed(f"OS error for {self._argument}") from err


class SystemMonitorSwapCoordinator(MonitorCoordinator[sswap]):
    """A System monitor Swap Data Update Coordinator."""

    def update_data(self) -> sswap:
        """Fetch data."""
        swap: sswap = self._psutil.swap_memory()
        _LOGGER.debug("sswap: %s", swap)
        return swap


class SystemMonitorMemoryCoordinator(MonitorCoordinator[VirtualMemory]):
    """A System monitor Memory Data Update Coordinator."""

    def update_data(self) -> VirtualMemory:
        """Fetch data."""
        memory = self._psutil.virtual_memory()
        _LOGGER.debug("memory: %s", memory)
        return VirtualMemory(
            memory.total, memory.available, memory.percent, memory.used, memory.free
        )


class SystemMonitorNetIOCoordinator(MonitorCoordinator[dict[str, snetio]]):
    """A System monitor Network IO Data Update Coordinator."""

    def update_data(self) -> dict[str, snetio]:
        """Fetch data."""
        io_counters: dict[str, snetio] = self._psutil.net_io_counters(pernic=True)
        _LOGGER.debug("io_counters: %s", io_counters)
        return io_counters


class SystemMonitorNetAddrCoordinator(MonitorCoordinator[dict[str, list[snicaddr]]]):
    """A System monitor Network Address Data Update Coordinator."""

    def update_data(self) -> dict[str, list[snicaddr]]:
        """Fetch data."""
        addresses: dict[str, list[snicaddr]] = self._psutil.net_if_addrs()
        _LOGGER.debug("ip_addresses: %s", addresses)
        return addresses


class SystemMonitorLoadCoordinator(
    MonitorCoordinator[tuple[float, float, float] | None]
):
    """A System monitor Load Data Update Coordinator."""

    def update_data(self) -> tuple[float, float, float] | None:
        """Coordinator is not async."""

    async def _async_update_data(self) -> tuple[float, float, float] | None:
        """Fetch data."""
        return os.getloadavg()


class SystemMonitorProcessorCoordinator(MonitorCoordinator[float | None]):
    """A System monitor Processor Data Update Coordinator."""

    def update_data(self) -> float | None:
        """Coordinator is not async."""

    async def _async_update_data(self) -> float | None:
        """Get cpu usage.

        Unlikely the rest of the coordinators, this one is async
        since it does not block and we need to make sure it runs
        in the same thread every time as psutil checks the thread
        tid and compares it against the previous one.
        """
        cpu_percent: float = self._psutil.cpu_percent(interval=None)
        _LOGGER.debug("cpu_percent: %s", cpu_percent)
        if cpu_percent > 0.0:
            return cpu_percent
        return None


class SystemMonitorBootTimeCoordinator(MonitorCoordinator[datetime]):
    """A System monitor Processor Data Update Coordinator."""

    def update_data(self) -> datetime:
        """Fetch data."""
        boot_time = dt_util.utc_from_timestamp(self._psutil.boot_time())
        _LOGGER.debug("boot time: %s", boot_time)
        return boot_time


class SystemMonitorProcessCoordinator(MonitorCoordinator[list[Process]]):
    """A System monitor Process Data Update Coordinator."""

    def update_data(self) -> list[Process]:
        """Fetch data."""
        processes = self._psutil.process_iter()
        _LOGGER.debug("processes: %s", processes)
        return list(processes)


class SystemMonitorCPUtempCoordinator(MonitorCoordinator[dict[str, list[shwtemp]]]):
    """A System monitor CPU Temperature Data Update Coordinator."""

    def update_data(self) -> dict[str, list[shwtemp]]:
        """Fetch data."""
        try:
            temps: dict[str, list[shwtemp]] = self._psutil.sensors_temperatures()
            _LOGGER.debug("temps: %s", temps)
            return temps
        except AttributeError as err:
            raise UpdateFailed("OS does not provide temperature sensors") from err
