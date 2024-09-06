"""Device tracker for MyBMW vehicles."""

from __future__ import annotations

import logging
from typing import Any

from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BMWConfigEntry
from .const import ATTR_DIRECTION
from .coordinator import BMWDataUpdateCoordinator
from .entity import BMWBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BMWConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MyBMW tracker from config entry."""
    coordinator = config_entry.runtime_data.coordinator
    entities: list[BMWDeviceTracker] = []

    for vehicle in coordinator.account.vehicles:
        entities.append(BMWDeviceTracker(coordinator, vehicle))
        if not vehicle.is_vehicle_tracking_enabled:
            _LOGGER.info(
                (
                    "Tracking is (currently) disabled for vehicle %s (%s), defaulting"
                    " to unknown"
                ),
                vehicle.name,
                vehicle.vin,
            )
    async_add_entities(entities)


class BMWDeviceTracker(BMWBaseEntity, TrackerEntity):
    """MyBMW device tracker."""

    _attr_force_update = False
    _attr_translation_key = "car"
    _attr_icon = "mdi:car"

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
    ) -> None:
        """Initialize the Tracker."""
        super().__init__(coordinator, vehicle)

        self._attr_unique_id = vehicle.vin
        self._attr_name = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {ATTR_DIRECTION: self.vehicle.vehicle_location.heading}

    @property
    def latitude(self) -> float | None:
        """Return latitude value of the device."""
        return (
            self.vehicle.vehicle_location.location[0]
            if self.vehicle.is_vehicle_tracking_enabled
            and self.vehicle.vehicle_location.location
            else None
        )

    @property
    def longitude(self) -> float | None:
        """Return longitude value of the device."""
        return (
            self.vehicle.vehicle_location.location[1]
            if self.vehicle.is_vehicle_tracking_enabled
            and self.vehicle.vehicle_location.location
            else None
        )

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS
