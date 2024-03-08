"""Matter sensors."""
from __future__ import annotations

from dataclasses import dataclass

from chip.clusters import Objects as clusters
from chip.clusters.Types import Nullable, NullValue
from matter_server.client.models.clusters import EveEnergyCluster

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter sensors from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.SENSOR, async_add_entities)


@dataclass(frozen=True)
class MatterSensorEntityDescription(SensorEntityDescription, MatterEntityDescription):
    """Describe Matter sensor entities."""


class MatterSensor(MatterEntity, SensorEntity):
    """Representation of a Matter sensor."""

    entity_description: MatterSensorEntityDescription

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value: Nullable | float | None
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        if value in (None, NullValue):
            value = None
        elif value_convert := self.entity_description.measurement_to_ha:
            value = value_convert(value)
        self._attr_native_value = value


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="TemperatureSensor",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            measurement_to_ha=lambda x: x / 100,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.TemperatureMeasurement.Attributes.MeasuredValue,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PressureSensor",
            native_unit_of_measurement=UnitOfPressure.KPA,
            device_class=SensorDeviceClass.PRESSURE,
            measurement_to_ha=lambda x: x / 10,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.PressureMeasurement.Attributes.MeasuredValue,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="FlowSensor",
            native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
            translation_key="flow",
            measurement_to_ha=lambda x: x / 10,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.FlowMeasurement.Attributes.MeasuredValue,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="HumiditySensor",
            native_unit_of_measurement=PERCENTAGE,
            device_class=SensorDeviceClass.HUMIDITY,
            measurement_to_ha=lambda x: x / 100,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.RelativeHumidityMeasurement.Attributes.MeasuredValue,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="LightSensor",
            native_unit_of_measurement=LIGHT_LUX,
            device_class=SensorDeviceClass.ILLUMINANCE,
            measurement_to_ha=lambda x: round(pow(10, ((x - 1) / 10000)), 1),
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.IlluminanceMeasurement.Attributes.MeasuredValue,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PowerSource",
            native_unit_of_measurement=PERCENTAGE,
            device_class=SensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            # value has double precision
            measurement_to_ha=lambda x: int(x / 2),
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.PowerSource.Attributes.BatPercentRemaining,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EveEnergySensorWatt",
            device_class=SensorDeviceClass.POWER,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(EveEnergyCluster.Attributes.Watt,),
        # Add OnOff Attribute as optional attribute to poll
        # the primary value when the relay is toggled
        optional_attributes=(clusters.OnOff.Attributes.OnOff,),
        should_poll=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EveEnergySensorVoltage",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(EveEnergyCluster.Attributes.Voltage,),
        should_poll=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EveEnergySensorWattAccumulated",
            device_class=SensorDeviceClass.ENERGY,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=3,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        entity_class=MatterSensor,
        required_attributes=(EveEnergyCluster.Attributes.WattAccumulated,),
        should_poll=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EveEnergySensorWattCurrent",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(EveEnergyCluster.Attributes.Current,),
        # Add OnOff Attribute as optional attribute to poll
        # the primary value when the relay is toggled
        optional_attributes=(clusters.OnOff.Attributes.OnOff,),
        should_poll=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="CarbonDioxideSensor",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.CarbonDioxideConcentrationMeasurement.Attributes.MeasuredValue,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PM1Sensor",
            native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            device_class=SensorDeviceClass.PM1,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.Pm1ConcentrationMeasurement.Attributes.MeasuredValue,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PM25Sensor",
            native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.Pm25ConcentrationMeasurement.Attributes.MeasuredValue,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PM10Sensor",
            native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            device_class=SensorDeviceClass.PM10,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.Pm10ConcentrationMeasurement.Attributes.MeasuredValue,
        ),
    ),
]
