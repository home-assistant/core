"""Sensor platform for Aqvify integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pyaqvify import AqvifyDeviceData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AqvifyConfigEntry, AqvifyCoordinator
from .entity import AqvifyBaseEntity

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AqvifySensorEntityDescription(SensorEntityDescription):
    """Description of an Aqvify sensor entity."""

    value_fn: Callable[[AqvifyDeviceData], StateType | datetime | None]


ENTITIES: tuple[AqvifySensorEntityDescription, ...] = (
    AqvifySensorEntityDescription(
        key="meter_value",
        translation_key="meter_value",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=2,
        value_fn=lambda value: value.meter_value,
    ),
    AqvifySensorEntityDescription(
        key="water_level",
        translation_key="water_level",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=2,
        value_fn=lambda value: value.water_level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AqvifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aqvify sensor entities from a config entry."""
    async_add_entities(
        AqvifySensor(entry.runtime_data, description, device_key)
        for description in ENTITIES
        for device_key in entry.runtime_data.data.devices.devices
    )


class AqvifySensor(AqvifyBaseEntity, SensorEntity):
    """Representation of an Aqvify sensor entity."""

    entity_description: AqvifySensorEntityDescription

    def __init__(
        self,
        coordinator: AqvifyCoordinator,
        description: AqvifySensorEntityDescription,
        device_key: str,
    ) -> None:
        """Initialize the Aqvify sensor."""
        super().__init__(coordinator, description, device_key)

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data.device_data[self.device_key]
        )
