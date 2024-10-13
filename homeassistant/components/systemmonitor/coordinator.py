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


@dataclass(frozen=True, kw_only=True, slots=True)
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
        disk_usage = None
        if self.disk_usage:
            disk_usage = {k: str(v) for k, v in self.disk_usage.items()}
        io_counters = None
        if self.io_counters:
            io_counters = {k: str(v) for k, v in self.io_counters.items()}
        addresses = None
        if self.addresses:
            addresses = {k: str(v) for k, v in self.addresses.items()}
        temperatures = None
        if self.temperatures:
            temperatures = {k: str(v) for k, v in self.temperatures.items()}
        return {
            "disk_usage": disk_usage,
            "swap": str(self.swap),
            "memory": str(self.memory),
            "io_counters": io_counters,
            "addresses": addresses,
            "load": str(self.load),
            "cpu_percent": str(self.cpu_percent),
            "boot_time": str(self.boot_time),
            "processes": str(self.processes),
            "temperatures": temperatures,
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
        self.boot_time: datetime | None = None

        self._initial_update: bool = True
        self.update_subscribers: dict[tuple[str, str], set[str]] = (
            self.set_subscribers_tuples(arguments)
        )

    def set_subscribers_tuples(
        self, arguments: list[str]
    ) -> dict[tuple[str, str], set[str]]:
        """Set tuples in subscribers dictionary."""
        _disk_defaults: dict[tuple[str, str], set[str]] = {}
        for argument in arguments:
            _disk_defaults[("disks", argument)] = set()
        return {
            **_disk_defaults,
            ("swap", ""): set(),
            ("memory", ""): set(),
            ("io_counters", ""): set(),
            ("addresses", ""): set(),
            ("load", ""): set(),
            ("cpu_percent", ""): set(),
            ("boot", ""): set(),
            ("processes", ""): set(),
            ("temperatures", ""): set(),
        }

    async def _async_update_data(self) -> SensorData:
        """Fetch data."""
        _LOGGER.debug("Update list is: %s", self.update_subscribers)

        _data = await self.hass.async_add_executor_job(self.update_data)

        load: tuple = (None, None, None)
        if self.update_subscribers[("load", "")] or self._initial_update:
            load = os.getloadavg()
            _LOGGER.debug("Load: %s", load)

        cpu_percent: float | None = None
        if self.update_subscribers[("cpu_percent", "")] or self._initial_update:
            cpu_percent = self._psutil.cpu_percent(interval=None)
            _LOGGER.debug("cpu_percent: %s", cpu_percent)

        self._initial_update = False
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
            if self.update_subscribers[("disks", argument)] or self._initial_update:
                try:
                    usage: sdiskusage = self._psutil.disk_usage(argument)
                    _LOGGER.debug("sdiskusagefor %s: %s", argument, usage)
                except PermissionError as err:
                    _LOGGER.warning(
                        "No permission to access %s, error %s", argument, err
                    )
                except OSError as err:
                    _LOGGER.warning("OS error for %s, error %s", argument, err)
                else:
                    disks[argument] = usage

        swap: sswap | None = None
        if self.update_subscribers[("swap", "")] or self._initial_update:
            swap = self._psutil.swap_memory()
            _LOGGER.debug("sswap: %s", swap)

        memory = None
        if self.update_subscribers[("memory", "")] or self._initial_update:
            memory = self._psutil.virtual_memory()
            _LOGGER.debug("memory: %s", memory)
            memory = VirtualMemory(
                memory.total, memory.available, memory.percent, memory.used, memory.free
            )

        io_counters: dict[str, snetio] | None = None
        if self.update_subscribers[("io_counters", "")] or self._initial_update:
            io_counters = self._psutil.net_io_counters(pernic=True)
            _LOGGER.debug("io_counters: %s", io_counters)

        addresses: dict[str, list[snicaddr]] | None = None
        if self.update_subscribers[("addresses", "")] or self._initial_update:
            addresses = self._psutil.net_if_addrs()
            _LOGGER.debug("ip_addresses: %s", addresses)

        if self._initial_update:
            # Boot time only needs to refresh on first pass
            self.boot_time = dt_util.utc_from_timestamp(self._psutil.boot_time())
            _LOGGER.debug("boot time: %s", self.boot_time)

        processes = None
        if self.update_subscribers[("processes", "")] or self._initial_update:
            processes = self._psutil.process_iter()
            _LOGGER.debug("processes: %s", processes)
            processes = list(processes)

        temps: dict[str, list[shwtemp]] = {}
        if self.update_subscribers[("temperatures", "")] or self._initial_update:
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
            "boot_time": self.boot_time,
            "processes": processes,
            "temperatures": temps,
        }
