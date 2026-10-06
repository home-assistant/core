"""Sensor platform for the LoJack integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from lojack_api.models import Location

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import LoJackConfigEntry
from .entity import LoJackEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LoJackSensorEntityDescription(SensorEntityDescription):
    """Describes LoJack sensor."""

    value_fn: Callable[[Location], StateType | datetime | None]


SENSORS: tuple[LoJackSensorEntityDescription, ...] = (
    LoJackSensorEntityDescription(
        key="odometer",
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda data: data.odometer,
    ),
    LoJackSensorEntityDescription(
        key="speed",
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.speed,
    ),
    LoJackSensorEntityDescription(
        key="battery_voltage",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.battery_voltage,
    ),
    LoJackSensorEntityDescription(
        key="location_last_reported",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.timestamp,
    ),
)


class LoJackSensor(LoJackEntity, SensorEntity):
    """Representation of a LoJack sensor."""

    entity_description: LoJackSensorEntityDescription

    @override
    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the sensor value from the latest location data."""
        location = self.coordinator.data
        return self.entity_description.value_fn(location)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LoJackConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LoJack sensors from a config entry."""
    async_add_entities(
        LoJackSensor(coordinator, description)
        for coordinator in entry.runtime_data.coordinators
        for description in SENSORS
    )
