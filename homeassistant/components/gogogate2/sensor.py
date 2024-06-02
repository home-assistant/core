"""Support for Gogogate2 garage Doors."""

from __future__ import annotations

from itertools import chain

from ismartgate.common import AbstractDoor, get_configured_doors

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import GoGoGate2Entity, get_data_update_coordinator, sensor_unique_id
from .coordinator import DeviceDataUpdateCoordinator

SENSOR_ID_WIRED = "WIRE"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the config entry."""
    data_update_coordinator = get_data_update_coordinator(hass, config_entry)

    sensors = chain(
        [
            DoorSensorBattery(config_entry, data_update_coordinator, door)
            for door in get_configured_doors(data_update_coordinator.data)
            if door.sensorid and door.sensorid != SENSOR_ID_WIRED
        ],
        [
            DoorSensorTemperature(config_entry, data_update_coordinator, door)
            for door in get_configured_doors(data_update_coordinator.data)
            if door.sensorid and door.sensorid != SENSOR_ID_WIRED
        ],
    )
    async_add_entities(sensors)


class DoorSensorEntity(GoGoGate2Entity, SensorEntity):
    """Base class for door sensor entities."""

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = super().extra_state_attributes
        door = self.door
        if door.sensorid is not None:
            attrs["sensor_id"] = door.sensorid
        return attrs


class DoorSensorBattery(DoorSensorEntity):
    """Battery sensor entity for gogogate2 door sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        config_entry: ConfigEntry,
        data_update_coordinator: DeviceDataUpdateCoordinator,
        door: AbstractDoor,
    ) -> None:
        """Initialize the object."""
        unique_id = sensor_unique_id(config_entry, door, "battery")
        super().__init__(config_entry, data_update_coordinator, door, unique_id)

    @property
    def name(self):
        """Return the name of the door."""
        return f"{self.door.name} battery"

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self.door.voltage  # This is a percentage, not an absolute voltage


class DoorSensorTemperature(DoorSensorEntity):
    """Temperature sensor entity for gogogate2 door sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        config_entry: ConfigEntry,
        data_update_coordinator: DeviceDataUpdateCoordinator,
        door: AbstractDoor,
    ) -> None:
        """Initialize the object."""
        unique_id = sensor_unique_id(config_entry, door, "temperature")
        super().__init__(config_entry, data_update_coordinator, door, unique_id)

    @property
    def name(self):
        """Return the name of the door."""
        return f"{self.door.name} temperature"

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self.door.temperature
