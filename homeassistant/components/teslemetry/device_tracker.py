"""Device tracker platform for Teslemetry integration."""

from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeslemetryConfigEntry
from .entity import TeslemetryVehicleEntity
from .models import TeslemetryVehicleData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Teslemetry device tracker platform from a config entry."""

    async_add_entities(
        klass(vehicle)
        for klass in (
            TeslemetryDeviceTrackerLocationEntity,
            TeslemetryDeviceTrackerRouteEntity,
        )
        for vehicle in entry.runtime_data.vehicles
    )


class TeslemetryDeviceTrackerEntity(TeslemetryVehicleEntity, TrackerEntity):
    """Base class for Teslemetry tracker entities."""

    lat_key: str
    lon_key: str

    def __init__(
        self,
        vehicle: TeslemetryVehicleData,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(vehicle, self.key)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the device tracker."""

        self._attr_available = (
            self.get(self.lat_key, False) is not None
            and self.get(self.lon_key, False) is not None
        )

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return self.get(self.lat_key)

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return self.get(self.lon_key)


class TeslemetryDeviceTrackerLocationEntity(TeslemetryDeviceTrackerEntity):
    """Vehicle location device tracker class."""

    key = "location"
    lat_key = "drive_state_latitude"
    lon_key = "drive_state_longitude"


class TeslemetryDeviceTrackerRouteEntity(TeslemetryDeviceTrackerEntity):
    """Vehicle navigation device tracker class."""

    key = "route"
    lat_key = "drive_state_active_route_latitude"
    lon_key = "drive_state_active_route_longitude"

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        location = self.get("drive_state_active_route_destination")
        if location == "Home":
            return STATE_HOME
        return location
