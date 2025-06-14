"""Device Tracker platform for Tessie integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TessieConfigEntry
from .const import (
    ATTR_DESTINATION,
    ATTR_LATITUDE,
    ATTR_LOCALE,
    ATTR_LONGITUDE,
    SERVICE_SET_NAVIGATION,
)
from .entity import TessieEntity
from .models import TessieVehicleData

NAV_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional(ATTR_DESTINATION): cv.string,
        vol.Optional(ATTR_LATITUDE): vol.Coerce(float),
        vol.Optional(ATTR_LONGITUDE): vol.Coerce(float),
        vol.Optional(ATTR_LOCALE, default="en-US"): cv.string,
    }
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_NAVIGATION,
        NAV_SCHEMA,
        "async_set_navigation",
    )


class TessieDeviceTrackerEntity(TessieEntity, TrackerEntity):
    """Base class for Tessie Tracker Entities."""

    def __init__(
        self,
        vehicle: TessieVehicleData,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(vehicle, self.key)


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
