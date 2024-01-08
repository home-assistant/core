"""DataUpdateCoordinators for the System monitor integration."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterator
from datetime import datetime
import logging
import os
import socket
from typing import TypeVar

import psutil
from psutil._common import sdiskusage, shwtemp, snetio, snicaddr, sswap
from psutil._pslinux import svmem

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

IO_COUNTER = {
    "network_out": 0,
    "network_in": 1,
    "packets_out": 2,
    "packets_in": 3,
    "throughput_network_out": 0,
    "throughput_network_in": 1,
}
IF_ADDRS_FAMILY = {"ipv4_address": socket.AF_INET, "ipv6_address": socket.AF_INET6}
# There might be additional keys to be added for different
# platforms / hardware combinations.
# Taken from last version of "glances" integration before they moved to
# a generic temperature sensor logic.
# https://github.com/home-assistant/core/blob/5e15675593ba94a2c11f9f929cdad317e27ce190/homeassistant/components/glances/sensor.py#L199
CPU_SENSOR_PREFIXES = [
    "amdgpu 1",
    "aml_thermal",
    "Core 0",
    "Core 1",
    "CPU Temperature",
    "CPU",
    "cpu-thermal 1",
    "cpu_thermal 1",
    "exynos-therm 1",
    "Package id 0",
    "Physical id 0",
    "radeon 1",
    "soc-thermal 1",
    "soc_thermal 1",
    "Tctl",
    "cpu0-thermal",
    "cpu0_thermal",
    "k10temp 1",
]

_dataT = TypeVar(
    "_dataT",
    bound=bool
    | datetime
    | dict[str, list[shwtemp]]
    | dict[str, list[snicaddr]]
    | dict[str, snetio]
    | float
    | int
    | Iterator[psutil.Process]
    | sswap
    | str
    | svmem
    | tuple[float, float, float]
    | sdiskusage
    | None,
)


class MonitorCoordinator(DataUpdateCoordinator[_dataT]):
    """A System monitor Base Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {self.__repr__}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )

    async def _async_update_data(self) -> _dataT:
        """Fetch data."""
        return await self.hass.async_add_executor_job(self.update_data)

    @abstractmethod
    def update_data(self) -> _dataT:
        """To be extended by data update coordinators."""


class SystemMonitorDiskCoordinator(MonitorCoordinator[sdiskusage]):
    """A System monitor Disk Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, argument: str) -> None:
        """Initialize the disk coordinator."""
        super().__init__(hass)
        self._argument = argument

    def update_data(self) -> sdiskusage:
        """Fetch data."""
        return psutil.disk_usage(self._argument)


class SystemMonitorSwapCoordinator(MonitorCoordinator[sswap]):
    """A System monitor Swap Data Update Coordinator."""

    def update_data(self) -> sswap:
        """Fetch data."""
        return psutil.swap_memory()


class SystemMonitorMemoryCoordinator(MonitorCoordinator[svmem]):
    """A System monitor Memory Data Update Coordinator."""

    def update_data(self) -> svmem:
        """Fetch data."""
        return psutil.virtual_memory()


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


class SystemMonitorProcessCoordinator(MonitorCoordinator[Iterator[psutil.Process]]):
    """A System monitor Process Data Update Coordinator."""

    def update_data(self) -> Iterator[psutil.Process]:
        """Fetch data."""
        return psutil.process_iter()


class SystemMonitorCPUtempCoordinator(MonitorCoordinator[dict[str, list[shwtemp]]]):
    """A System monitor CPU Temperature Data Update Coordinator."""

    def update_data(self) -> dict[str, list[shwtemp]]:
        """Fetch data."""
        return psutil.sensors_temperatures()
