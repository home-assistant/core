"""Sensor platform for Aqvify integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pyaqvify import AqvifyDeviceData, AqvifyHourAggregatedValues

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import UnitOfLength, UnitOfVolume, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AqvifyConfigEntry
from .entity import AqvifyAggrEntity, AqvifyEntity

# Coordinator is used to centralize the data updates.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AqvifySensorEntityDescription(SensorEntityDescription):
    """Description of an Aqvify sensor entity."""

    value_fn: Callable[
        [AqvifyDeviceData | AqvifyHourAggregatedValues], float | int | None
    ]


ENTITIES: tuple[AqvifySensorEntityDescription, ...] = (
    AqvifySensorEntityDescription(
        key="meter_value",
        translation_key="meter_value",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=2,
        value_fn=lambda value: value.meter_value,  # type: ignore[union-attr]
    ),
    AqvifySensorEntityDescription(
        key="water_level",
        translation_key="water_level",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        suggested_display_precision=2,
        value_fn=lambda value: value.water_level,  # type: ignore[union-attr]
    ),
)


ENTITIES_AGGR: tuple[AqvifySensorEntityDescription, ...] = (
    AqvifySensorEntityDescription(
        key="in_flow",
        translation_key="in_flow",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        suggested_display_precision=0,
        value_fn=lambda value: value.in_flow,  # type: ignore[union-attr]
    ),
    AqvifySensorEntityDescription(
        key="out_volume",
        translation_key="out_volume",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.WATER,
        suggested_display_precision=1,
        value_fn=lambda value: value.out_volume,  # type: ignore[union-attr]
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AqvifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aqvify sensor entities from a config entry."""
    async_add_entities(
        AqvifySensor(entry.runtime_data.coordinator, device_key, description)
        for description in ENTITIES
        for device_key in entry.runtime_data.coordinator.data.devices.devices
    )
    async_add_entities(
        AqvifyAggrSensor(
            entry.runtime_data.aggr_data_coordinator, device_key, description
        )
        for description in ENTITIES_AGGR
        for device_key in entry.runtime_data.aggr_data_coordinator.data
    )


class AqvifySensor(AqvifyEntity, SensorEntity):
    """Representation of an Aqvify sensor entity."""

    entity_description: AqvifySensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data.device_data[self.device_key]
        )


class AqvifyAggrSensor(AqvifyAggrEntity, SensorEntity):
    """Representation of an Aqvify aggregation sensor entity."""

    entity_description: AqvifySensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self.device_key])

    # @property
    # def last_reset(self) -> datetime | None:
    #     """These values reset every update."""
    #     if self.entity_description.key == "out_volume":
    #         return dt_util.parse_datetime(
    #             self.coordinator.data[self.device_key].date_time
    #         )
    #     return None
