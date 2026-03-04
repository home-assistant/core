"""Sensor platform for Kiosker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import KioskerConfigEntry
from .coordinator import KioskerDataUpdateCoordinator
from .entity import KioskerEntity

# Limit concurrent updates to prevent overwhelming the API
PARALLEL_UPDATES = 3


@dataclass(frozen=True, kw_only=True)
class KioskerSensorEntityDescription(SensorEntityDescription):
    """Kiosker sensor description."""

    value_fn: Callable[[Any], StateType | datetime]


SENSORS: tuple[KioskerSensorEntityDescription, ...] = (
    KioskerSensorEntityDescription(
        key="batteryLevel",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.battery_level,
    ),
    KioskerSensorEntityDescription(
        key="lastInteraction",
        translation_key="last_interaction",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: x.last_interaction,
    ),
    KioskerSensorEntityDescription(
        key="lastMotion",
        translation_key="last_motion",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: x.last_motion,
    ),
    KioskerSensorEntityDescription(
        key="ambientLight",
        translation_key="ambient_light",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.ambient_light,
    ),
    KioskerSensorEntityDescription(
        key="lastUpdate",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: x.last_update,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KioskerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kiosker sensors based on a config entry."""
    coordinator = entry.runtime_data

    # Create all sensors - they will handle missing data gracefully
    async_add_entities(
        KioskerSensor(coordinator, description) for description in SENSORS
    )


class KioskerSensor(KioskerEntity, SensorEntity):
    """Representation of a Kiosker sensor."""

    entity_description: KioskerSensorEntityDescription

    def __init__(
        self,
        coordinator: KioskerDataUpdateCoordinator,
        description: KioskerSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the native value of the sensor."""
        if not self.coordinator.data:
            return None

        status = self.coordinator.data.status
        if not status:
            return None

        return self.entity_description.value_fn(status)
