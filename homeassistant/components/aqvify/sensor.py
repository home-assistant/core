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

from .coordinator import AqvifyConfigEntry
from .entity import AqvifyBaseEntity

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AqvifySensorEntityDescription(SensorEntityDescription):
    """Description of an Aqvify sensor entity."""

    value_fn: Callable[[AqvifyDeviceData], float | int | None]


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

    coordinator = entry.runtime_data
    added_devices: set[str] = set()

    def _async_add_new_devices() -> None:
        nonlocal added_devices
        new_devices_set, current_devices = coordinator.async_add_devices(added_devices)
        added_devices = current_devices

        async_add_entities(
            AqvifySensor(coordinator, description, device_key)
            for description in ENTITIES
            for device_key in entry.runtime_data.data.devices.devices
            if device_key in new_devices_set
        )

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))
    _async_add_new_devices()


class AqvifySensor(AqvifyBaseEntity, SensorEntity):
    """Representation of an Aqvify sensor entity."""

    entity_description: AqvifySensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data.device_data[self.device_key]
        )
