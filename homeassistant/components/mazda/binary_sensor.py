"""Platform for Mazda binary sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN


@dataclass
class MazdaBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    # Suffix to be appended to the vehicle name to obtain the binary sensor name
    name_suffix: str

    # Function to determine the value for this binary sensor, given the coordinator data
    value: Callable[[dict], bool]


@dataclass
class MazdaBinarySensorEntityDescription(
    BinarySensorEntityDescription, MazdaBinarySensorRequiredKeysMixin
):
    """Describes a Mazda binary sensor entity."""

    # Function to determine whether the vehicle supports this binary sensor, given the coordinator data
    is_supported: Callable[[dict], bool] = lambda data: True

    # Function to return extra state attributes, given the coordinator data
    state_attributes: Callable[[dict], dict] | None = None


def _plugged_in_supported(data):
    """Determine if 'plugged in' binary sensor is supported."""
    return (
        data["isElectric"] and data["evStatus"]["chargeInfo"]["pluggedIn"] is not None
    )


def _charging_supported(data):
    """Determine if 'charging' binary sensor is supported."""
    return data["isElectric"] and data["evStatus"]["chargeInfo"]["charging"] is not None


def _doors_open(data):
    """Determine if at least one vehicle door is open."""
    door_status = data["status"]["doors"]
    return (
        door_status["driverDoorOpen"]
        or door_status["passengerDoorOpen"]
        or door_status["rearLeftDoorOpen"]
        or door_status["rearRightDoorOpen"]
    )


def _doors_state_attributes(data):
    """Get state attributes for the vehicle doors."""
    door_status = data["status"]["doors"]

    return {
        "driver_door_open": door_status["driverDoorOpen"],
        "passenger_door_open": door_status["passengerDoorOpen"],
        "rear_left_door_open": door_status["rearLeftDoorOpen"],
        "rear_right_door_open": door_status["rearRightDoorOpen"],
    }


BINARY_SENSOR_ENTITIES = [
    MazdaBinarySensorEntityDescription(
        key="doors",
        name_suffix="Doors",
        icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        value=_doors_open,
        state_attributes=_doors_state_attributes,
    ),
    MazdaBinarySensorEntityDescription(
        key="trunk",
        name_suffix="Trunk",
        icon="mdi:car-back",
        device_class=BinarySensorDeviceClass.DOOR,
        value=lambda data: data["status"]["doors"]["trunkOpen"],
    ),
    MazdaBinarySensorEntityDescription(
        key="hood",
        name_suffix="Hood",
        icon="mdi:car",
        device_class=BinarySensorDeviceClass.DOOR,
        value=lambda data: data["status"]["doors"]["hoodOpen"],
    ),
    MazdaBinarySensorEntityDescription(
        key="ev_plugged_in",
        name_suffix="Plugged In",
        device_class=BinarySensorDeviceClass.PLUG,
        is_supported=_plugged_in_supported,
        value=lambda data: data["evStatus"]["chargeInfo"]["pluggedIn"],
    ),
    MazdaBinarySensorEntityDescription(
        key="ev_charging",
        name_suffix="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_supported=_charging_supported,
        value=lambda data: data["evStatus"]["chargeInfo"]["charging"],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities: list[BinarySensorEntity] = []

    for index, data in enumerate(coordinator.data):
        for description in BINARY_SENSOR_ENTITIES:
            if description.is_supported(data):
                entities.append(
                    MazdaBinarySensorEntity(client, coordinator, index, description)
                )

    async_add_entities(entities)


class MazdaBinarySensorEntity(MazdaEntity, BinarySensorEntity):
    """Representation of a Mazda vehicle binary sensor."""

    entity_description: MazdaBinarySensorEntityDescription

    def __init__(self, client, coordinator, index, description):
        """Initialize Mazda binary sensor."""
        super().__init__(client, coordinator, index)
        self.entity_description = description

        self._attr_name = f"{self.vehicle_name} {description.name_suffix}"
        self._attr_unique_id = f"{self.vin}_{description.key}"

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self.entity_description.value(self.data)

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes of the binary sensor."""
        if self.entity_description.state_attributes is not None:
            return self.entity_description.state_attributes(self.data)

        return None
