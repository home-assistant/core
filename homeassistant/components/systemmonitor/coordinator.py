"""DataUpdateCoordinators for the System monitor integration."""
from __future__ import annotations

import logging
import os

import psutil
from psutil._common import sdiskusage, shwtemp, snetio, snicaddr, sswap
from psutil._pslinux import svmem

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .sensor import CPU_SENSOR_PREFIXES

_LOGGER = logging.getLogger(__name__)


class SystemMonitorDiskCoordinator(DataUpdateCoordinator[sdiskusage]):
    """A System monitor Disk Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, argument: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )
        self._argument = argument

    async def _async_update_data(self) -> sdiskusage:
        """Fetch data."""
        return psutil.disk_usage(self._argument)


class SystemMonitorSwapCoordinator(DataUpdateCoordinator[sswap]):
    """A System monitor Swap Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def _async_update_data(self) -> sswap:
        """Fetch data."""
        return psutil.swap_memory()


class SystemMonitorMemoryCoordinator(DataUpdateCoordinator[svmem]):
    """A System monitor Memory Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def _async_update_data(self) -> svmem:
        """Fetch data."""
        return psutil.virtual_memory()


class SystemMonitorNetIOCoordinator(DataUpdateCoordinator[dict[str, snetio]]):
    """A System monitor Network IO Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, snetio]:
        """Fetch data."""
        return psutil.net_io_counters(pernic=True)


class SystemMonitorNetAddrCoordinator(DataUpdateCoordinator[dict[str, list[snicaddr]]]):
    """A System monitor Network Address Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, list[snicaddr]]:
        """Fetch data."""
        return psutil.net_if_addrs()


class SystemMonitorLoadCoordinator(DataUpdateCoordinator[tuple[float, float, float]]):
    """A System monitor Load Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def _async_update_data(self) -> tuple[float, float, float]:
        """Fetch data."""
        return os.getloadavg()


class SystemMonitorCPUtempCoordinator(DataUpdateCoordinator[float | None]):
    """A System monitor CPU Temperature Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL
        )

    async def _async_update_data(self) -> float | None:
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
        raise UpdateFailed("No temp sensors")
