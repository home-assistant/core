"""Data update coordinator for the LoJack integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from lojack_api import ApiError, AuthenticationError, LoJackClient
from lojack_api.device import Vehicle
from lojack_api.models import Location

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import LoJackConfigEntry


@dataclass
class LoJackVehicleData:
    """Data class for vehicle data."""

    device_id: str
    name: str | None
    vin: str | None
    make: str | None
    model: str | None
    year: int | None
    latitude: float | None
    longitude: float | None
    accuracy: float | None
    address: str | None
    heading: float | None
    timestamp: datetime | None


def get_device_name(vehicle: LoJackVehicleData) -> str:
    """Get a human-readable name for a vehicle."""
    parts = [
        str(vehicle.year) if vehicle.year else None,
        vehicle.make,
        vehicle.model,
    ]
    name = " ".join(p for p in parts if p)
    return name or vehicle.name or "Vehicle"


class LoJackCoordinator(DataUpdateCoordinator[LoJackVehicleData]):
    """Class to manage fetching LoJack data for a single vehicle."""

    config_entry: LoJackConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: LoJackClient,
        entry: ConfigEntry,
        vehicle: Vehicle,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.vehicle = vehicle

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{vehicle.id}",
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
            config_entry=entry,
        )

    async def _async_update_data(self) -> LoJackVehicleData:
        """Fetch location data for this vehicle."""
        try:
            location: Location | None = await self.vehicle.get_location(force=True)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except ApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        return LoJackVehicleData(
            device_id=self.vehicle.id,
            name=self.vehicle.name,
            vin=self.vehicle.vin,
            make=self.vehicle.make,
            model=self.vehicle.model,
            year=self.vehicle.year,
            latitude=location.latitude if location else None,
            longitude=location.longitude if location else None,
            accuracy=location.accuracy if location else None,
            address=location.address if location else None,
            heading=location.heading if location else None,
            timestamp=location.timestamp if location else None,
        )
