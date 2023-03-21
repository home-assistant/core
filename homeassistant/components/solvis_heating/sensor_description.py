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
        key="time",
        name="last update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=as_local,
    ),
    SolvisMaxSensorEntityDescription(
        key="S1",
        name="temperature buffer top",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S2",
        name="temperature warm water station",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S3",
        name="temperature buffer reference",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S4",
        name="temperature H buffer top",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S5",
        name="temperature solar flow",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S6",
        name="temperature solar return",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S7",
        name="solar pressure",
        native_unit_of_measurement=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S8",
        name="temperature solar panel",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S9",
        name="temperature H buffer bottom",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S10",
        name="temperature outside",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S11",
        name="temperature circulation",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S12",
        name="temperature heating circuit 1 flow",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S13",
        name="temperature heating circuit 2 flow",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S17",
        name="volume solar pump",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITER_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="S18",
        name="volume warm water",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITER_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="SL",
        name="solar power",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SolvisMaxSensorEntityDescription(
        key="SE",
        name="solar yield",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SolvisMaxSensorEntityDescription(
        key="Z4",
        name="runtime solar pump",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
)
