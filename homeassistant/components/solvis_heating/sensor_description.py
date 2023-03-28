"""Sensordescriptions for Solvis Max Sensor Data."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.util.dt import as_local


@dataclass
class SolvisMaxSensorEntityDescription(SensorEntityDescription):
    """Describes SolvisMax sensor entity."""

    value: Callable[[float | int], float] | Callable[[datetime], datetime] | None = None


SENSOR_TYPES: tuple[SolvisMaxSensorEntityDescription, ...] = (
    SolvisMaxSensorEntityDescription(
        key="last_update",
        name="last update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=as_local,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_buffer_top",
        name="temperature buffer top",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_warm_water_station",
        name="temperature warm water station",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_buffer_reference",
        name="temperature buffer reference",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_buffer_heating_top",
        name="temperature H buffer top",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_solar_flow",
        name="temperature solar flow",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_solar_return",
        name="temperature solar return",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_solar_diff_flow_return",
        name="temperature solar diff flow-return",
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="solar_pressure",
        name="solar pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_solar_panel",
        name="temperature solar panel",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_buffer_heating_bottom",
        name="temperature H buffer bottom",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_outside",
        name="temperature outside",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_circulation",
        name="temperature circulation",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_heating_circuit_1_flow",
        name="temperature heating circuit 1 flow",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="temperature_heating_circuit_2_flow",
        name="temperature heating circuit 2 flow",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="volume_stream_solar",
        name="volume stream solar",
        icon="mdi:pump",
        # native_unit_of_measurement="l/h", --> UnitOfVolumeFlowRate.LITER_PER_HOUR currently not implemented
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="volume_stream_warm_water",
        name="volume stream warm water",
        icon="mdi:pump",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITER_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="solar_power",
        name="solar power",
        translation_key="solar_power",
        icon="mdi:solar-power-variant-outline",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="solar_yield",
        name="solar yield",
        translation_key="solar_yield",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SolvisMaxSensorEntityDescription(
        key="runtime_solar_pump",
        name="runtime solar pump",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
)
