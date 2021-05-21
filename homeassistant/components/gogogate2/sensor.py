"""Support for Gogogate2 garage Doors."""
from __future__ import annotations

from itertools import chain

from ismartgate.common import AbstractDoor, get_configured_doors

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import (
    DeviceDataUpdateCoordinator,
    GoGoGate2Entity,
    get_data_update_coordinator,
    sensor_unique_id,
)

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


class DoorSensorBattery(GoGoGate2Entity, SensorEntity):
    """Battery sensor entity for gogogate2 door sensor."""

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
        return f"{self._get_door().name} battery"

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self):
        """Return the state of the entity."""
        door = self._get_door()
        return door.voltage  # This is a percentage, not an absolute voltage

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        door = self._get_door()
        if door.sensorid is not None:
            return {"door_id": door.door_id, "sensor_id": door.sensorid}
        return None


class DoorSensorTemperature(GoGoGate2Entity, SensorEntity):
    """Temperature sensor entity for gogogate2 door sensor."""

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
        return f"{self._get_door().name} temperature"

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def state(self):
        """Return the state of the entity."""
        door = self._get_door()
        return door.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        door = self._get_door()
        if door.sensorid is not None:
            return {"door_id": door.door_id, "sensor_id": door.sensorid}
        return None
