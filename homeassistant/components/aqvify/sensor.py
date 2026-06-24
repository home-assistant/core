"""Sensor platform for Aqvify integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from pyaqvify import AqvifyDeviceData, AqvifyHourAggregatedValues

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AqvifyConfigEntry
from .entity import AqvifyAggrEntity, AqvifyEntity

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AqvifySensorEntityDescription(SensorEntityDescription):
    """Description of an Aqvify sensor entity."""

    value_fn: Callable[[AqvifyDeviceData], float | int | None]


@dataclass(frozen=True, kw_only=True)
class AqvifySensorAggrEntityDescription(SensorEntityDescription):
    """Description of an Aqvify sensor entity for aggregated data."""

    value_fn: Callable[[AqvifyHourAggregatedValues], float | int | None]


ENTITIES: tuple[AqvifySensorEntityDescription, ...] = (
    AqvifySensorEntityDescription(
        key="level_from_sensor",
        translation_key="level_from_sensor",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=2,
        value_fn=lambda value: value.meter_value,
    ),
    AqvifySensorEntityDescription(
        key="level_from_top",
        translation_key="level_from_top",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=2,
        value_fn=lambda value: value.water_level,
    ),
    AqvifySensorEntityDescription(
        key="available_volume",
        translation_key="available_volume",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        suggested_display_precision=0,
        value_fn=lambda value: value.volume,
    ),
    AqvifySensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        value_fn=lambda value: value.temperature,
        entity_registry_enabled_default=False,
    ),
)


ENTITIES_AGGR: tuple[AqvifySensorAggrEntityDescription, ...] = (
    AqvifySensorAggrEntityDescription(
        key="in_flow",
        translation_key="in_flow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        suggested_display_precision=0,
        value_fn=lambda value: value.in_flow,
    ),
    AqvifySensorAggrEntityDescription(
        key="out_volume",
        translation_key="out_volume",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.WATER,
        suggested_display_precision=1,
        value_fn=lambda value: value.out_volume,
    ),
    AqvifySensorAggrEntityDescription(
        key="ground_water_level",
        translation_key="ground_water_level",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=2,
        value_fn=lambda value: value.valid_ground_water_level,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AqvifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aqvify sensor entities from a config entry."""

    coordinator = entry.runtime_data.coordinator
    aggr_data_coordinator = entry.runtime_data.aggr_data_coordinator
    added_devices: set[str] = set()

    def _async_add_new_devices() -> None:
        nonlocal added_devices
        new_devices_set, current_devices = coordinator.async_add_devices(added_devices)
        added_devices = current_devices

        entities: list[AqvifySensor | AqvifyAggrSensor] = [
            AqvifySensor(coordinator, device_key, description)
            for description in ENTITIES
            for device_key in new_devices_set
        ]

        entities.extend(
            [
                AqvifyAggrSensor(aggr_data_coordinator, device_key, description)
                for description in ENTITIES_AGGR
                for device_key in new_devices_set
            ]
        )
        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))
    _async_add_new_devices()


class AqvifySensor(AqvifyEntity, SensorEntity):
    """Representation of an Aqvify sensor entity."""

    entity_description: AqvifySensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data.device_data[self.device_key]
        )


class AqvifyAggrSensor(AqvifyAggrEntity, SensorEntity):
    """Representation of an Aqvify aggregation sensor entity."""

    entity_description: AqvifySensorAggrEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self.device_key])
