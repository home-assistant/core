"""Sensor platform for Kiosker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from kiosker import Status

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

# Coordinator-based platform; no per-entity polling concurrency needed
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KioskerSensorEntityDescription(SensorEntityDescription):
    """Kiosker sensor description."""

    value_fn: Callable[[Status], StateType | datetime | None]


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
        return self.entity_description.value_fn(self.coordinator.data.status)
