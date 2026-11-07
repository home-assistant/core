"""Coordinator polling a GBFS system's stations."""

from dataclasses import dataclass
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


@dataclass(frozen=True, kw_only=True)
class GbfsData:
    """The current stations and vehicle types of a GBFS system, keyed by ID."""

    stations: dict[str, Station]
    vehicle_types: dict[str, VehicleType]


class GbfsCoordinator(DataUpdateCoordinator[GbfsData]):
    """Fetch every station and the vehicle types of one GBFS system."""

    config_entry: GbfsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GbfsConfigEntry,
        feed: GbfsFeedHandle,
        system: SystemInfo,
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

    @override
    async def _async_update_data(self) -> GbfsData:
        """Fetch stations and vehicle types."""
        try:
            stations = await self.feed.get_stations()
            vehicle_types = await self.feed.get_vehicle_types()
        except MobilityFeedsError as err:
            raise UpdateFailed(f"Error fetching GBFS data: {err}") from err
        return GbfsData(
            stations={station.id: station for station in stations},
            vehicle_types={
                vehicle_type.id: vehicle_type for vehicle_type in vehicle_types
            },
        )
