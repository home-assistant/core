"""Support for Aladdin Connect Genie sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from genie_partner_sdk.model import GarageDoor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AladdinConnectConfigEntry, AladdinConnectCoordinator
from .entity import AladdinConnectEntity


@dataclass(frozen=True, kw_only=True)
class AladdinConnectSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for Aladdin Connect."""

    value_fn: Callable[[GarageDoor], float | None]


SENSOR_TYPES: tuple[AladdinConnectSensorEntityDescription, ...] = (
    AladdinConnectSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda garage_door: garage_door.battery_level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AladdinConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aladdin Connect sensor devices."""
    coordinators = entry.runtime_data

    async_add_entities(
        AladdinConnectSensor(coordinator, description)
        for coordinator in coordinators.values()
        for description in SENSOR_TYPES
    )


class AladdinConnectSensor(AladdinConnectEntity, SensorEntity):
    """A sensor implementation for Aladdin Connect device."""

    entity_description: AladdinConnectSensorEntityDescription

    def __init__(
        self,
        coordinator: AladdinConnectCoordinator,
        entity_description: AladdinConnectSensorEntityDescription,
    ) -> None:
        """Initialize the Aladdin Connect sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.data.unique_id}-{entity_description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
