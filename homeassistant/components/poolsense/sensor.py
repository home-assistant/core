"""Sensor platform for the PoolSense sensor."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PoolSenseConfigEntry
from .entity import PoolSenseEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="Chlorine",
        translation_key="chlorine",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    SensorEntityDescription(
        key="pH",
        device_class=SensorDeviceClass.PH,
    ),
    SensorEntityDescription(
        key="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    SensorEntityDescription(
        key="Water Temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key="water_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="Last Seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="Chlorine High",
        translation_key="chlorine_high",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    SensorEntityDescription(
        key="Chlorine Low",
        translation_key="chlorine_low",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    SensorEntityDescription(
        key="pH High",
        translation_key="ph_high",
    ),
    SensorEntityDescription(
        key="pH Low",
        translation_key="ph_low",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PoolSenseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        PoolSenseSensor(coordinator, description) for description in SENSOR_TYPES
    )


class PoolSenseSensor(PoolSenseEntity, SensorEntity):
    """Sensor representing poolsense data."""

    @property
    def native_value(self) -> StateType:
        """State of the sensor."""
        return self.coordinator.data[self.entity_description.key]
