"""DataUpdateCoordinators for the System monitor integration."""
from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
import logging
import os
import socket
from typing import TypeVar

import psutil
from psutil._common import sdiskusage, shwtemp, sswap
from psutil._pslinux import svmem

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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
    bound=sdiskusage
    | sswap
    | svmem
    | int
    | float
    | str
    | tuple[float, float, float]
    | datetime
    | bool
    | None,
)


class MonitorCoordinator(DataUpdateCoordinator[_dataT]):
    """A System monitor Base Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, type_: str, argument: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {type_}_{argument}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )
        self._type = type_
        self._argument = argument

    async def _async_update_data(self) -> _dataT:
        """Fetch data."""
        return await self.hass.async_add_executor_job(self.update_data)

    @abstractmethod
    def update_data(self) -> _dataT:
        """To be extended by data update coordinators."""


class SystemMonitorDiskCoordinator(MonitorCoordinator[sdiskusage]):
    """A System monitor Disk Data Update Coordinator."""

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


class SystemMonitorNetIOCoordinator(MonitorCoordinator[int]):
    """A System monitor Network IO Data Update Coordinator."""

    def update_data(self) -> int:
        """Fetch data."""
        counters = psutil.net_io_counters(pernic=True)
        if self._argument in counters:
            return counters[self._argument][IO_COUNTER[self._type]]
        raise UpdateFailed(f"NIC {self._argument} could not be found")


class SystemMonitorNetThroughputCoordinator(MonitorCoordinator[float | None]):
    """A System monitor Network Throughput Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, type_: str, argument: str) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, type_, argument)
        self._value: float | None = None
        self._update_time: datetime | None = None

    def update_data(self) -> float | None:
        """Fetch data."""
        counters = psutil.net_io_counters(pernic=True)
        if self._argument in counters:
            counter = counters[self._argument][IO_COUNTER[self._type]]
            now = dt_util.utcnow()
            if self._value and self._value < counter:
                return round(
                    (counter - self._value)
                    / 1000**2
                    / (now - (self._update_time or now)).total_seconds(),
                    3,
                )
            self._update_time = now
            self._value = counter
            return None
        raise UpdateFailed(f"NIC {self._argument} could not be found")


class SystemMonitorNetAddrCoordinator(MonitorCoordinator[str]):
    """A System monitor Network Address Data Update Coordinator."""

    def update_data(self) -> str:
        """Fetch data."""
        addresses = psutil.net_if_addrs()
        if self._argument in addresses:
            for addr in addresses[self._argument]:
                if addr.family == IF_ADDRS_FAMILY[self._type]:
                    return addr.address
        raise UpdateFailed(f"NIC {self._argument} could not be found for {self._type}")


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


class SystemMonitorProcessCoordinator(MonitorCoordinator[bool]):
    """A System monitor Process Data Update Coordinator."""

    def update_data(self) -> bool:
        """Fetch data."""
        for proc in psutil.process_iter():
            try:
                if self._argument.lower() == proc.name().lower():
                    return True
            except psutil.NoSuchProcess as err:
                _LOGGER.warning(
                    "Failed to load process with ID: %s, old name: %s",
                    err.pid,
                    err.name,
                )
        return False


class SystemMonitorCPUtempCoordinator(MonitorCoordinator[float]):
    """A System monitor CPU Temperature Data Update Coordinator."""

    def update_data(self) -> float:
        """Fetch data."""
        entry: shwtemp
        temps = psutil.sensors_temperatures()

        for name, entries in temps.items():
            for i, entry in enumerate(entries, start=1):
                # In case the label is empty (e.g. on Raspberry PI 4),
                # construct it ourself here based on the sensor key name.
                _label = f"{name} {i}" if not entry.label else entry.label
                # check both name and label because some systems embed cpu# in the
                # name, which makes label not match because label adds cpu# at end.
                if _label in CPU_SENSOR_PREFIXES or name in CPU_SENSOR_PREFIXES:
                    return round(entry.current, 1)
        raise UpdateFailed("No temp sensors available")
