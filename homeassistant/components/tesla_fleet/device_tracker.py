"""Device Tracker platform for Tesla Fleet integration."""

from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import TeslaFleetVehicleEntity
from .models import TeslaFleetVehicleData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tesla Fleet device tracker platform from a config entry."""

    async_add_entities(
        klass(vehicle)
        for klass in (
            TeslaFleetDeviceTrackerLocationEntity,
            TeslaFleetDeviceTrackerRouteEntity,
        )
        for vehicle in entry.runtime_data.vehicles
    )


class TeslaFleetDeviceTrackerEntity(
    TeslaFleetVehicleEntity, TrackerEntity, RestoreEntity
):
    """Base class for Tesla Fleet device tracker entities."""

    def __init__(
        self,
        vehicle: TeslaFleetVehicleData,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(vehicle, self.key)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (
            (state := await self.async_get_last_state()) is not None
            and self._attr_latitude is None
            and self._attr_longitude is None
        ):
            self._attr_latitude = state.attributes.get("latitude")
            self._attr_longitude = state.attributes.get("longitude")


class TeslaFleetDeviceTrackerLocationEntity(TeslaFleetDeviceTrackerEntity):
    """Vehicle Location device tracker Class."""

    key = "location"

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

        self._attr_latitude = self.get("drive_state_latitude")
        self._attr_longitude = self.get("drive_state_longitude")
        self._attr_available = not (
            self.get("drive_state_longitude", False) is None
            or self.get("drive_state_latitude", False) is None
        )


class TeslaFleetDeviceTrackerRouteEntity(TeslaFleetDeviceTrackerEntity):
    """Vehicle Navigation device tracker Class."""

    key = "route"

    def _async_update_attrs(self) -> None:
        """Update the attributes of the device tracker."""
        self._attr_latitude = self.get("drive_state_active_route_latitude")
        self._attr_longitude = self.get("drive_state_active_route_longitude")
        self._attr_available = not (
            self.get("drive_state_active_route_longitude", False) is None
            or self.get("drive_state_active_route_latitude", False) is None
        )

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location of the device."""
        location = self.get("drive_state_active_route_destination")
        if location == "Home":
            return STATE_HOME
        return location
