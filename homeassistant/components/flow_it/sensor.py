"""Sensor platform for Flow-it."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from flow_it_api.const import FilterStatus
from flow_it_api.models import MachineStatusResponse

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlowItConfigEntry
from .entity import FlowItVmcEntity


@dataclass(frozen=True, kw_only=True)
class FlowItVmcSensorEntityDescription(SensorEntityDescription):
    """Describes Flow-it sensor entity."""

    value_fn: Callable[[MachineStatusResponse], float | int | str | None]


SENSORS: tuple[FlowItVmcSensorEntityDescription, ...] = (
    FlowItVmcSensorEntityDescription(
        key="temperature_in",
        translation_key="temperature_in",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.data.mode.temperatureIn_celsius,
    ),
    FlowItVmcSensorEntityDescription(
        key="temperature_out",
        translation_key="temperature_out",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.data.mode.temperatureOut_celsius,
    ),
    FlowItVmcSensorEntityDescription(
        key="humidity_in",
        translation_key="humidity_in",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            val * 100 if (val := data.data.mode.humidityIn) is not None else None
        ),
    ),
    FlowItVmcSensorEntityDescription(
        key="humidity_out",
        translation_key="humidity_out",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: (
            val * 100 if (val := data.data.mode.humidityOut) is not None else None
        ),
    ),
    FlowItVmcSensorEntityDescription(
        key="iaq",
        translation_key="iaq",
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.iaq,
    ),
    FlowItVmcSensorEntityDescription(
        key="pressure_in",
        translation_key="pressure_in",
        native_unit_of_measurement=UnitOfPressure.PA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.pressureIn,
    ),
    FlowItVmcSensorEntityDescription(
        key="pressure_out",
        translation_key="pressure_out",
        native_unit_of_measurement=UnitOfPressure.PA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.pressureOut,
    ),
    FlowItVmcSensorEntityDescription(
        key="hepa_filter_status",
        translation_key="hepa_filter_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.name.lower() for status in FilterStatus],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.filter.hepa.status.name.lower(),
    ),
    FlowItVmcSensorEntityDescription(
        key="g4_filter_status",
        translation_key="g4_filter_status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.name.lower() for status in FilterStatus],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.data.filter.g4.status.name.lower(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlowItConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flow-it sensors."""
    data = config_entry.runtime_data
    async_add_entities(
        FlowItVmcSensor(data.coordinator, data.vmc, description)
        for description in SENSORS
    )


class FlowItVmcSensor(FlowItVmcEntity, SensorEntity):
    """Flow-it sensor entity."""

    entity_description: FlowItVmcSensorEntityDescription

    @override
    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.state)
