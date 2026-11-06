"""Coordinator polling a GBFS system's stations."""

import logging
from typing import override

from aiomobilitydatabase.feeds import (
    GbfsFeedHandle,
    MobilityFeedsError,
    Station,
    SystemInfo,
    VehicleType,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type GbfsConfigEntry = ConfigEntry[GbfsCoordinator]


class GbfsCoordinator(DataUpdateCoordinator[dict[str, Station]]):
    """Fetch every station of one GBFS system, keyed by station ID."""

    config_entry: GbfsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GbfsConfigEntry,
        feed: GbfsFeedHandle,
        system: SystemInfo,
        vehicle_types: list[VehicleType],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=UPDATE_INTERVAL,
        )
        self.feed = feed
        self.system = system
        self.vehicle_types = vehicle_types

    @override
    async def _async_update_data(self) -> dict[str, Station]:
        """Fetch station information and status."""
        try:
            stations = await self.feed.get_stations()
        except MobilityFeedsError as err:
            raise UpdateFailed(f"Error fetching GBFS stations: {err}") from err
        return {station.id: station for station in stations}
