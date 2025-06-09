"""Support for Minut Point sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, UnitOfSoundPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PointConfigEntry
from .coordinator import PointDataUpdateCoordinator
from .entity import MinutPointEntity

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        suggested_display_precision=1,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="humidity",
        suggested_display_precision=1,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="sound_pressure",
        suggested_display_precision=1,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
        native_unit_of_measurement=UnitOfSoundPressure.WEIGHTED_DECIBEL_A,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PointConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Point's sensors based on a config entry."""

    coordinator = config_entry.runtime_data

    def async_discover_sensor(device_id: str) -> None:
        """Discover and add a discovered sensor."""
        async_add_entities(
            MinutPointSensor(coordinator, device_id, description)
            for description in SENSOR_TYPES
        )

    coordinator.new_device_callbacks.append(async_discover_sensor)

    async_add_entities(
        MinutPointSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSOR_TYPES
    )


class MinutPointSensor(MinutPointEntity, SensorEntity):
    """The platform class required by Home Assistant."""

    def __init__(
        self,
        coordinator: PointDataUpdateCoordinator,
        device_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"point.{device_id}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.data[self.device_id].get(self.entity_description.key)
