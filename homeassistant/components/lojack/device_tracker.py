"""Device tracker platform for the LoJack integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LoJackConfigEntry, LoJackCoordinator
from .entity import LoJackEntity

ATTR_ADDRESS = "address"
ATTR_BATTERY_VOLTAGE = "battery_voltage"
ATTR_COLOR = "color"
ATTR_ENGINE_HOURS = "engine_hours"
ATTR_HEADING = "heading"
ATTR_LICENSE_PLATE = "license_plate"
ATTR_MAKE = "make"
ATTR_MODEL = "model"
ATTR_ODOMETER = "odometer"
ATTR_SPEED = "speed"
ATTR_TIMESTAMP = "timestamp"
ATTR_VIN = "vin"
ATTR_YEAR = "year"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LoJack device trackers."""
    async_add_entities(
        LoJackDeviceTracker(coordinator)
        for coordinator in entry.runtime_data.coordinators.values()
    )


class LoJackDeviceTracker(LoJackEntity, TrackerEntity):
    """Representation of a LoJack device tracker."""

    _attr_name = None
    _attr_translation_key = "vehicle"

    def __init__(self, coordinator: LoJackCoordinator) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}"
        self._update_attrs()

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device tracker."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return the latitude of the device."""
        if self.vehicle_data:
            return self.vehicle_data.latitude
        return None

    @property
    def longitude(self) -> float | None:
        """Return the longitude of the device."""
        if self.vehicle_data:
            return self.vehicle_data.longitude
        return None

    @property
    def location_accuracy(self) -> int:
        """Return the location accuracy of the device."""
        if self.vehicle_data and self.vehicle_data.accuracy is not None:
            return int(self.vehicle_data.accuracy)
        return 0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()

    @callback
    def _update_attrs(self) -> None:
        """Update entity attributes from coordinator data."""
        attrs: dict[str, str | float | None] = {}

        if not self.vehicle_data:
            self._attr_extra_state_attributes = attrs
            return

        vehicle = self.vehicle_data

        if vehicle.vin:
            attrs[ATTR_VIN] = vehicle.vin
        if vehicle.make:
            attrs[ATTR_MAKE] = vehicle.make
        if vehicle.model:
            attrs[ATTR_MODEL] = vehicle.model
        if vehicle.year:
            attrs[ATTR_YEAR] = vehicle.year
        if vehicle.color:
            attrs[ATTR_COLOR] = vehicle.color
        if vehicle.license_plate:
            attrs[ATTR_LICENSE_PLATE] = vehicle.license_plate
        if vehicle.odometer is not None:
            attrs[ATTR_ODOMETER] = round(float(vehicle.odometer), 1)
        if vehicle.speed is not None:
            attrs[ATTR_SPEED] = round(float(vehicle.speed), 1)
        if vehicle.heading is not None:
            attrs[ATTR_HEADING] = float(vehicle.heading)
        if vehicle.battery_voltage is not None:
            attrs[ATTR_BATTERY_VOLTAGE] = round(float(vehicle.battery_voltage), 2)
        if vehicle.engine_hours is not None:
            attrs[ATTR_ENGINE_HOURS] = round(float(vehicle.engine_hours), 1)
        if vehicle.address:
            attrs[ATTR_ADDRESS] = vehicle.address
        if vehicle.timestamp:
            attrs[ATTR_TIMESTAMP] = vehicle.timestamp

        self._attr_extra_state_attributes = attrs

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to hass."""
        await super().async_added_to_hass()
        self._update_attrs()
