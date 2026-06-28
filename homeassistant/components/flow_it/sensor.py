"""Sensor platform for Flow-it."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from flow_it_api.models import MachineStatusResponse

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlowItConfigEntry
from .entity import FlowItVmcEntity


@dataclass(frozen=True, kw_only=True)
class FlowItVmcSensorEntityDescription(SensorEntityDescription):
    """Describes Flow-it sensor entity."""

    value_fn: Callable[[MachineStatusResponse], float | int | str | None]
    flow_direction: str | None = None


SENSORS: tuple[FlowItVmcSensorEntityDescription, ...] = (
    FlowItVmcSensorEntityDescription(
        key="temperature_in",
        name="Temperature In",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.temperatureIn_celsius,
        flow_direction="inflow",
    ),
    FlowItVmcSensorEntityDescription(
        key="temperature_out",
        name="Temperature Out",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.temperatureOut_celsius,
        flow_direction="outflow",
    ),
    FlowItVmcSensorEntityDescription(
        key="humidity_in",
        name="Humidity In",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.humidityIn * 100,
        flow_direction="inflow",
    ),
    FlowItVmcSensorEntityDescription(
        key="humidity_out",
        name="Humidity Out",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.humidityOut * 100,
        flow_direction="outflow",
    ),
    FlowItVmcSensorEntityDescription(
        key="iaq",
        name="IAQ",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.iaq,
    ),
    FlowItVmcSensorEntityDescription(
        key="pressure_in",
        name="Pressure In",
        native_unit_of_measurement=UnitOfPressure.PA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.pressureIn,
        flow_direction="inflow",
    ),
    FlowItVmcSensorEntityDescription(
        key="pressure_out",
        name="Pressure Out",
        native_unit_of_measurement=UnitOfPressure.PA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.data.mode.pressureOut,
        flow_direction="outflow",
    ),
    FlowItVmcSensorEntityDescription(
        key="hepa_filter_status",
        name="HEPA Filter Status",
        value_fn=lambda data: data.data.filter.hepa.status.name,
    ),
    FlowItVmcSensorEntityDescription(
        key="g4_filter_status",
        name="G4 Filter Status",
        value_fn=lambda data: data.data.filter.g4.status.name,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlowItConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Flow-it sensors."""
    data = config_entry.runtime_data
    coordinator = data.coordinator
    vmc = data.vmc

    async_add_entities(
        FlowItVmcSensor(coordinator, vmc, description) for description in SENSORS
    )


class FlowItVmcSensor(FlowItVmcEntity, SensorEntity):
    """Flow-it sensor entity."""

    entity_description: FlowItVmcSensorEntityDescription

    def __init__(
        self,
        coordinator: Any,
        vmc: Any,
        description: FlowItVmcSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vmc)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.name}_{description.key}"

    @override
    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @override
    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return entity specific state attributes."""
        if self.entity_description.flow_direction:
            return {"flow_direction": self.entity_description.flow_direction}
        return None
