"""Platform for Mazda binary sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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

    # Function to determine the value for this binary sensor, given the coordinator data
    value_fn: Callable[[dict[str, Any]], bool]


@dataclass
class MazdaBinarySensorEntityDescription(
    BinarySensorEntityDescription, MazdaBinarySensorRequiredKeysMixin
):
    """Describes a Mazda binary sensor entity."""

    # Function to determine whether the vehicle supports this binary sensor, given the coordinator data
    is_supported: Callable[[dict[str, Any]], bool] = lambda data: True


def _plugged_in_supported(data):
    """Determine if 'plugged in' binary sensor is supported."""
    return (
        data["isElectric"] and data["evStatus"]["chargeInfo"]["pluggedIn"] is not None
    )


BINARY_SENSOR_ENTITIES = [
    MazdaBinarySensorEntityDescription(
        key="driver_door",
        translation_key="driver_door",
        icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: data["status"]["doors"]["driverDoorOpen"],
    ),
    MazdaBinarySensorEntityDescription(
        key="passenger_door",
        translation_key="passenger_door",
        icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: data["status"]["doors"]["passengerDoorOpen"],
    ),
    MazdaBinarySensorEntityDescription(
        key="rear_left_door",
        translation_key="rear_left_door",
        icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: data["status"]["doors"]["rearLeftDoorOpen"],
    ),
    MazdaBinarySensorEntityDescription(
        key="rear_right_door",
        translation_key="rear_right_door",
        icon="mdi:car-door",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: data["status"]["doors"]["rearRightDoorOpen"],
    ),
    MazdaBinarySensorEntityDescription(
        key="trunk",
        translation_key="trunk",
        icon="mdi:car-back",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: data["status"]["doors"]["trunkOpen"],
    ),
    MazdaBinarySensorEntityDescription(
        key="hood",
        translation_key="hood",
        icon="mdi:car",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda data: data["status"]["doors"]["hoodOpen"],
    ),
    MazdaBinarySensorEntityDescription(
        key="ev_plugged_in",
        translation_key="ev_plugged_in",
        device_class=BinarySensorDeviceClass.PLUG,
        is_supported=_plugged_in_supported,
        value_fn=lambda data: data["evStatus"]["chargeInfo"]["pluggedIn"],
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

    async_add_entities(
        MazdaBinarySensorEntity(client, coordinator, index, description)
        for index, data in enumerate(coordinator.data)
        for description in BINARY_SENSOR_ENTITIES
        if description.is_supported(data)
    )


class MazdaBinarySensorEntity(MazdaEntity, BinarySensorEntity):
    """Representation of a Mazda vehicle binary sensor."""

    entity_description: MazdaBinarySensorEntityDescription

    def __init__(self, client, coordinator, index, description):
        """Initialize Mazda binary sensor."""
        super().__init__(client, coordinator, index)
        self.entity_description = description

        self._attr_unique_id = f"{self.vin}_{description.key}"

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.data)
