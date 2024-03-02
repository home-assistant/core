"""DataUpdateCoordinators for the System monitor integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from typing import Any, NamedTuple

from psutil import Process
from psutil._common import sdiskusage, shwtemp, snetio, snicaddr, sswap
import psutil_home_assistant as ha_psutil

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SensorData:
    """Sensor data."""

    disk_usage: dict[str, sdiskusage]
    swap: sswap
    memory: VirtualMemory
    io_counters: dict[str, snetio]
    addresses: dict[str, list[snicaddr]]
    load: tuple[float, float, float]
    cpu_percent: float | None
    boot_time: datetime
    processes: list[Process]
    temperatures: dict[str, list[shwtemp]]

    def as_dict(self) -> dict[str, Any]:
        """Return as dict."""
        return {
            "disk_usage": {k: str(v) for k, v in self.disk_usage.items()},
            "swap": str(self.swap),
            "memory": str(self.memory),
            "io_counters": {k: str(v) for k, v in self.io_counters.items()},
            "addresses": {k: str(v) for k, v in self.addresses.items()},
            "load": str(self.load),
            "cpu_percent": str(self.cpu_percent),
            "boot_time": str(self.boot_time),
            "processes": str(self.processes),
            "temperatures": {k: str(v) for k, v in self.temperatures.items()},
        }


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


class SystemMonitorCoordinator(TimestampDataUpdateCoordinator[SensorData]):
    """A System monitor Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        psutil_wrapper: ha_psutil.PsutilWrapper,
        arguments: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="System Monitor update coordinator",
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )
        self._psutil = psutil_wrapper.psutil
        self._arguments = arguments

    async def _async_update_data(self) -> SensorData:
        """Fetch data."""
        _data = await self.hass.async_add_executor_job(self.update_data)
        load = os.getloadavg()
        _LOGGER.debug("Load: %s", load)
        cpu_percent: float = self._psutil.cpu_percent(interval=None)
        _LOGGER.debug("cpu_percent: %s", cpu_percent)

        return SensorData(
            disk_usage=_data["disks"],
            swap=_data["swap"],
            memory=_data["memory"],
            io_counters=_data["io_counters"],
            addresses=_data["addresses"],
            load=load,
            cpu_percent=cpu_percent,
            boot_time=_data["boot_time"],
            processes=_data["processes"],
            temperatures=_data["temperatures"],
        )

    def update_data(self) -> dict[str, Any]:
        """To be extended by data update coordinators."""
        disks: dict[str, sdiskusage] = {}
        for argument in self._arguments:
            try:
                usage: sdiskusage = self._psutil.disk_usage(argument)
                _LOGGER.debug("sdiskusagefor %s: %s", argument, usage)
            except PermissionError as err:
                _LOGGER.warning("No permission to access %s, error %s", argument, err)
            except OSError as err:
                _LOGGER.warning("OS error for %s, error %s", argument, err)
            else:
                disks[argument] = usage
        swap: sswap = self._psutil.swap_memory()
        _LOGGER.debug("sswap: %s", swap)
        memory = self._psutil.virtual_memory()
        _LOGGER.debug("memory: %s", memory)
        memory = VirtualMemory(
            memory.total, memory.available, memory.percent, memory.used, memory.free
        )
        io_counters: dict[str, snetio] = self._psutil.net_io_counters(pernic=True)
        _LOGGER.debug("io_counters: %s", io_counters)
        addresses: dict[str, list[snicaddr]] = self._psutil.net_if_addrs()
        _LOGGER.debug("ip_addresses: %s", addresses)
        boot_time = dt_util.utc_from_timestamp(self._psutil.boot_time())
        _LOGGER.debug("boot time: %s", boot_time)
        processes = self._psutil.process_iter()
        _LOGGER.debug("processes: %s", processes)
        processes = list(processes)
        temps: dict[str, list[shwtemp]] = {}
        try:
            temps = self._psutil.sensors_temperatures()
            _LOGGER.debug("temps: %s", temps)
        except AttributeError:
            _LOGGER.debug("OS does not provide temperature sensors")
        return {
            "disks": disks,
            "swap": swap,
            "memory": memory,
            "io_counters": io_counters,
            "addresses": addresses,
            "boot_time": boot_time,
            "processes": processes,
            "temperatures": temps,
        }
