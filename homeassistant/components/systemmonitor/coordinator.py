"""DataUpdateCoordinators for the System monitor integration."""
from __future__ import annotations

from datetime import timedelta
from functools import cache
import logging
import os
from typing import Literal

import psutil
from psutil._common import sdiskusage, shwtemp, snetio, snicaddr, sswap
from psutil._pslinux import svmem

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .sensor import CPU_SENSOR_PREFIXES

_LOGGER = logging.getLogger(__name__)


class SystemMonitorDiskCoordinator(
    DataUpdateCoordinator[
        (
            sdiskusage
            | sswap
            | svmem
            | dict[str, snetio]
            | dict[str, list[snicaddr]]
            | tuple[float, float, float]
            | float
            | None
        )
    ]
):
    """A System monitor Data Update Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        type_: Literal["disk", "swap", "memory", "netio", "netaddr", "load", "cputemp"],
        argument: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL.seconds),
        )
        self._type = type_
        self._argument = argument

    async def _async_update_data(
        self,
    ) -> (
        sdiskusage
        | sswap
        | svmem
        | dict[str, snetio]
        | dict[str, list[snicaddr]]
        | tuple[float, float, float]
        | float
        | None
    ):
        """Fetch data."""

        if self._type == "disk":
            return _disk_usage(self._argument)
        if self._type == "swap":
            return _swap_memory()
        if self._type == "memory":
            return _virtual_memory()
        if self._type == "netio":
            return _net_io_counters()
        if self._type == "netaddr":
            return _net_if_addrs()
        if self._type == "load":
            return _getloadavg()
        if self._type == "cputemp":
            return _read_cpu_temperature()


@cache
def _disk_usage(path: str) -> sdiskusage:
    return psutil.disk_usage(path)


@cache
def _swap_memory() -> sswap:
    return psutil.swap_memory()


@cache
def _virtual_memory() -> svmem:
    return psutil.virtual_memory()


@cache
def _net_io_counters() -> dict[str, snetio]:
    return psutil.net_io_counters(pernic=True)


@cache
def _net_if_addrs() -> dict[str, list[snicaddr]]:
    return psutil.net_if_addrs()


@cache
def _getloadavg() -> tuple[float, float, float]:
    return os.getloadavg()


def _read_cpu_temperature() -> float | None:
    """Attempt to read CPU / processor temperature."""
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

    return None
