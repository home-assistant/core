"""Coordinate polling and commands for one Monoprice amplifier connection."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from pymonoprice import Monoprice, ZoneStatus
from serialx import SerialException

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from . import MonopriceConfigEntry

_LOGGER = logging.getLogger(__name__)
ZONE_IDS = tuple(unit * 10 + zone for unit in range(1, 4) for zone in range(1, 7))


class MonopriceCoordinator(DataUpdateCoordinator[dict[int, ZoneStatus | None]]):
    """Poll active zones, retaining failures separately for each zone."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MonopriceConfigEntry,
        client: Monoprice,
        startup_zones: tuple[int, ...],
    ) -> None:
        """Initialize the amplifier coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Monoprice",
            update_interval=timedelta(seconds=10),
        )
        self.client = client
        self._startup_zones: tuple[int, ...] | None = startup_zones
        # pymonoprice only locks single calls. Hold this lock for a whole poll or
        # a whole command with its read-back, so they cannot interleave.
        self._operation_lock = asyncio.Lock()

    @callback
    def async_finish_discovery(self) -> None:
        """Use entity contexts once startup discovery has completed."""
        self._startup_zones = None

    def _read_zone(self, zone: int) -> ZoneStatus | None:
        """Read one zone, returning None when it does not answer."""
        try:
            status = self.client.zone_status(zone)
        except SerialException, TimeoutError:
            status = None
        if status is None and self.data and self.data.get(zone) is not None:
            _LOGGER.warning("Could not update zone %d", zone)
        return status

    async def _async_read_zones(
        self, zones: tuple[int, ...]
    ) -> dict[int, ZoneStatus | None]:
        """Read zones one executor job each, while the caller holds the lock.

        Cancelling a poll on unload then stops after the read in flight. That
        read still completes, since a running serial call cannot be interrupted.
        """
        return {
            zone: await self.hass.async_add_executor_job(self._read_zone, zone)
            for zone in zones
        }

    @override
    async def _async_update_data(self) -> dict[int, ZoneStatus | None]:
        async with self._operation_lock:
            zones = self._startup_zones
            if zones is None:
                zones = tuple(sorted(set(self.async_contexts())))
            return await self._async_read_zones(zones)

    async def async_command(
        self, zone: int, command: Callable[..., Any], *args: Any
    ) -> None:
        """Serialize a command and its read-back with scheduled polling."""

        def send_and_read() -> dict[int, ZoneStatus | None]:
            command(*args)
            return {zone: self._read_zone(zone)}

        async with self._operation_lock:
            result = await self.hass.async_add_executor_job(send_and_read)
            self.data = {**self.data, **result}
            # A targeted read must not postpone polling the other zones.
            self.async_update_listeners()

    async def async_snapshot(self, zone: int) -> ZoneStatus | None:
        """Read a fresh snapshot without interleaving a command."""
        async with self._operation_lock:
            return await self.hass.async_add_executor_job(self.client.zone_status, zone)
