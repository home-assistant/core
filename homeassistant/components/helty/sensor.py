"""Sensor platform for the Helty Flow integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pyhelty import HeltyData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HeltyConfigEntry, HeltyDataUpdateCoordinator
from .entity import HeltyEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HeltySensorEntityDescription(SensorEntityDescription):
    """Describes a Helty sensor."""

    value_fn: Callable[[HeltyData], float | None]


SENSORS: tuple[HeltySensorEntityDescription, ...] = (
    HeltySensorEntityDescription(
        key="indoor_temperature",
        translation_key="indoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.indoor_temperature,
    ),
    HeltySensorEntityDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.outdoor_temperature,
    ),
    HeltySensorEntityDescription(
        key="indoor_humidity",
        translation_key="indoor_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.indoor_humidity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeltyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Helty sensors."""
    coordinator = entry.runtime_data
    async_add_entities(HeltySensor(coordinator, description) for description in SENSORS)


class HeltySensor(HeltyEntity, SensorEntity):
    """An environmental sensor reported by the ventilation unit."""

    entity_description: HeltySensorEntityDescription

    def __init__(
        self,
        coordinator: HeltyDataUpdateCoordinator,
        description: HeltySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current sensor reading."""
        return self.entity_description.value_fn(self.coordinator.data)
