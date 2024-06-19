"""Device Tracker platform for Tessie integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TessieConfigEntry
from .coordinator import TessieStateUpdateCoordinator
from .entity import TessieEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tessie device tracker platform from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        klass(vehicle)
        for klass in (
            TessieDeviceTrackerLocationEntity,
            TessieDeviceTrackerRouteEntity,
        )
        for vehicle in data.vehicles
    )


class TessieDeviceTrackerEntity(TessieEntity, TrackerEntity):
    """Base class for Tessie Tracker Entities."""

    def __init__(
        self,
        coordinator: TessieStateUpdateCoordinator,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, self.key)

    @property
    def source_type(self) -> SourceType | str:
        """Return the source type of the device tracker."""
        return SourceType.GPS


class TessieDeviceTrackerLocationEntity(TessieDeviceTrackerEntity):
    """Vehicle Location Device Tracker Class."""

    key = "location"

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the device tracker."""
        return self.get("drive_state_longitude")

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the device tracker."""
        return self.get("drive_state_latitude")

    @property
    def extra_state_attributes(self) -> dict[str, StateType] | None:
        """Return device state attributes."""
        return {
            "heading": self.get("drive_state_heading"),
            "speed": self.get("drive_state_speed"),
        }


class TessieDeviceTrackerRouteEntity(TessieDeviceTrackerEntity):
    """Vehicle Navigation Device Tracker Class."""

    key = "route"

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the device tracker."""
        return self.get("drive_state_active_route_longitude")

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the device tracker."""
        return self.get("drive_state_active_route_latitude")
