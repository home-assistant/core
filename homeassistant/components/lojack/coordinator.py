"""Data update coordinator for the LoJack integration."""

from __future__ import annotations

from datetime import timedelta
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


def get_device_name(vehicle: Vehicle) -> str:
    """Get a human-readable name for a vehicle."""
    parts = [
        str(vehicle.year) if vehicle.year else None,
        vehicle.make,
        vehicle.model,
    ]
    name = " ".join(p for p in parts if p)
    return name or vehicle.name or "Vehicle"


class LoJackCoordinator(DataUpdateCoordinator[Location]):
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

    async def _async_update_data(self) -> Location:
        """Fetch location data for this vehicle."""
        try:
            location = await self.vehicle.get_location(force=True)
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except ApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        if location is None:
            raise UpdateFailed("No location data available")
        return location
