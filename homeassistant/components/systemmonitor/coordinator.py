"""DataUpdateCoordinators for the System monitor integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import os
from typing import TYPE_CHECKING, Any, NamedTuple

from psutil import Process
from psutil._common import sbattery, sdiskusage, shwtemp, snetio, snicaddr, sswap
import psutil_home_assistant as ha_psutil

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_PROCESS, PROCESS_ERRORS

if TYPE_CHECKING:
    from . import SystemMonitorConfigEntry
from .util import read_fan_speed

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True, slots=True)
class SensorData:
    """Sensor data."""

    addresses: dict[str, list[snicaddr]]
    battery: sbattery | None
    boot_time: datetime
    cpu_percent: float | None
    disk_usage: dict[str, sdiskusage]
    fan_speed: dict[str, int]
    io_counters: dict[str, snetio]
    load: tuple[float, float, float]
    memory: VirtualMemory
    process_fds: dict[str, int]
    processes: list[Process]
    swap: sswap
    temperatures: dict[str, list[shwtemp]]

    def as_dict(self) -> dict[str, Any]:
        """Return as dict."""
        addresses = None
        if self.addresses:
            addresses = {k: str(v) for k, v in self.addresses.items()}
        disk_usage = None
        if self.disk_usage:
            disk_usage = {k: str(v) for k, v in self.disk_usage.items()}
        fan_speed = None
        if self.fan_speed:
            fan_speed = {k: str(v) for k, v in self.fan_speed.items()}
        io_counters = None
        if self.io_counters:
            io_counters = {k: str(v) for k, v in self.io_counters.items()}
        temperatures = None
        if self.temperatures:
            temperatures = {k: str(v) for k, v in self.temperatures.items()}

        return {
            "addresses": addresses,
            "battery": str(self.battery),
            "boot_time": str(self.boot_time),
            "cpu_percent": str(self.cpu_percent),
            "disk_usage": disk_usage,
            "fan_speed": fan_speed,
            "io_counters": io_counters,
            "load": str(self.load),
            "memory": str(self.memory),
            "process_fds": self.process_fds,
            "processes": str(self.processes),
            "swap": str(self.swap),
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

    config_entry: SystemMonitorConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SystemMonitorConfigEntry,
        psutil_wrapper: ha_psutil.PsutilWrapper,
        arguments: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
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
            ("addresses", ""): set(),
            ("battery", ""): set(),
            ("boot", ""): set(),
            ("cpu_percent", ""): set(),
            ("fan_speed", ""): set(),
            ("io_counters", ""): set(),
            ("load", ""): set(),
            ("memory", ""): set(),
            ("processes", ""): set(),
            ("swap", ""): set(),
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
            addresses=_data["addresses"],
            battery=_data["battery"],
            boot_time=_data["boot_time"],
            cpu_percent=cpu_percent,
            disk_usage=_data["disks"],
            fan_speed=_data["fan_speed"],
            io_counters=_data["io_counters"],
            load=load,
            memory=_data["memory"],
            process_fds=_data["process_fds"],
            processes=_data["processes"],
            swap=_data["swap"],
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

        selected_processes: list[Process] = []
        process_fds: dict[str, int] = {}
        if self.update_subscribers[("processes", "")] or self._initial_update:
            processes = self._psutil.process_iter()
            _LOGGER.debug("processes: %s", processes)
            user_options: list[str] = self.config_entry.options.get(
                BINARY_SENSOR_DOMAIN, {}
            ).get(CONF_PROCESS, [])
            for process in processes:
                try:
                    if (process_name := process.name()) in user_options:
                        selected_processes.append(process)
                        process_fds[process_name] = (
                            process_fds.get(process_name, 0) + process.num_fds()
                        )

                except PROCESS_ERRORS as err:
                    if not hasattr(err, "pid") or not hasattr(err, "name"):
                        _LOGGER.warning(
                            "Failed to load process: %s",
                            str(err),
                        )
                    else:
                        _LOGGER.warning(
                            "Failed to load process with ID: %s, old name: %s",
                            err.pid,
                            err.name,
                        )
                    continue
                except OSError as err:
                    _LOGGER.warning(
                        "OS error getting file descriptor count for process %s: %s",
                        process.pid if hasattr(process, "pid") else "unknown",
                        err,
                    )

        temps: dict[str, list[shwtemp]] = {}
        if self.update_subscribers[("temperatures", "")] or self._initial_update:
            try:
                temps = self._psutil.sensors_temperatures()
                _LOGGER.debug("temps: %s", temps)
            except AttributeError:
                _LOGGER.debug("OS does not provide temperature sensors")

        fan_speed: dict[str, int] = {}
        if self.update_subscribers[("fan_speed", "")] or self._initial_update:
            try:
                fan_sensors = self._psutil.sensors_fans()
                fan_speed = read_fan_speed(fan_sensors)
                _LOGGER.debug("fan_speed: %s", fan_speed)
            except AttributeError:
                _LOGGER.debug("OS does not provide fan sensors")

        battery: sbattery | None = None
        if self.update_subscribers[("battery", "")] or self._initial_update:
            try:
                battery = self._psutil.sensors_battery()
                _LOGGER.debug("battery: %s", battery)
            except AttributeError:
                _LOGGER.debug("OS does not provide battery sensors")

        return {
            "addresses": addresses,
            "battery": battery,
            "boot_time": self.boot_time,
            "disks": disks,
            "fan_speed": fan_speed,
            "io_counters": io_counters,
            "memory": memory,
            "process_fds": process_fds,
            "processes": selected_processes,
            "swap": swap,
            "temperatures": temps,
        }
