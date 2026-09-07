"""Sensor platform for Vizio SmartCast devices."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import VizioConfigEntry, VizioDeviceData
from .entity import VizioDescriptionEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VizioSensorEntityDescription(SensorEntityDescription):
    """Describes a Vizio sensor entity."""

    value_fn: Callable[[VizioDeviceData], int | None]


SENSORS: tuple[VizioSensorEntityDescription, ...] = (
    VizioSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.battery_level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VizioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vizio sensor entities."""
    coordinator = config_entry.runtime_data.device_coordinator
    if not coordinator.device.profile.has_battery:
        return

    async_add_entities(
        VizioSensor(config_entry, description) for description in SENSORS
    )


class VizioSensor(VizioDescriptionEntity, SensorEntity):
    """Sensor entity for battery-powered Vizio SmartCast devices."""

    entity_description: VizioSensorEntityDescription

    @property
    @override
    def native_value(self) -> int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
