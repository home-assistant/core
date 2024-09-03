"""Matter sensors."""

from __future__ import annotations

from dataclasses import dataclass

from chip.clusters import Objects as clusters
from chip.clusters.Types import Nullable, NullValue
from matter_server.common.custom_clusters import (
    EveCluster,
    NeoCluster,
    ThirdRealityMeteringCluster,
)

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

AIR_QUALITY_MAP = {
    clusters.AirQuality.Enums.AirQualityEnum.kExtremelyPoor: "extremely_poor",
    clusters.AirQuality.Enums.AirQualityEnum.kVeryPoor: "very_poor",
    clusters.AirQuality.Enums.AirQualityEnum.kPoor: "poor",
    clusters.AirQuality.Enums.AirQualityEnum.kFair: "fair",
    clusters.AirQuality.Enums.AirQualityEnum.kGood: "good",
    clusters.AirQuality.Enums.AirQualityEnum.kModerate: "moderate",
    clusters.AirQuality.Enums.AirQualityEnum.kUnknown: "unknown",
    clusters.AirQuality.Enums.AirQualityEnum.kUnknownEnumValue: "unknown",
}


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
        required_attributes=(EveCluster.Attributes.Watt,),
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
        required_attributes=(EveCluster.Attributes.Voltage,),
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
        required_attributes=(EveCluster.Attributes.WattAccumulated,),
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
        required_attributes=(EveCluster.Attributes.Current,),
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
            key="TotalVolatileOrganicCompoundsSensor",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.TotalVolatileOrganicCompoundsConcentrationMeasurement.Attributes.MeasuredValue,
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
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="AirQuality",
            translation_key="air_quality",
            device_class=SensorDeviceClass.ENUM,
            state_class=None,
            # convert to set first to remove the duplicate unknown value
            options=list(set(AIR_QUALITY_MAP.values())),
            measurement_to_ha=lambda x: AIR_QUALITY_MAP[x],
            icon="mdi:air-filter",
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.AirQuality.Attributes.AirQuality,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="CarbonMonoxideSensor",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
            device_class=SensorDeviceClass.CO,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.CarbonMonoxideConcentrationMeasurement.Attributes.MeasuredValue,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="NitrogenDioxideSensor",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
            device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.NitrogenDioxideConcentrationMeasurement.Attributes.MeasuredValue,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="OzoneConcentrationSensor",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
            device_class=SensorDeviceClass.OZONE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.OzoneConcentrationMeasurement.Attributes.MeasuredValue,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="HepaFilterCondition",
            native_unit_of_measurement=PERCENTAGE,
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="hepa_filter_condition",
            icon="mdi:filter-check",
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.HepaFilterMonitoring.Attributes.Condition,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ActivatedCarbonFilterCondition",
            native_unit_of_measurement=PERCENTAGE,
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="activated_carbon_filter_condition",
            icon="mdi:filter-check",
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ActivatedCarbonFilterMonitoring.Attributes.Condition,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ThirdRealityEnergySensorWatt",
            device_class=SensorDeviceClass.POWER,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
            measurement_to_ha=lambda x: x / 1000,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            ThirdRealityMeteringCluster.Attributes.InstantaneousDemand,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ThirdRealityEnergySensorWattAccumulated",
            device_class=SensorDeviceClass.ENERGY,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            suggested_display_precision=3,
            state_class=SensorStateClass.TOTAL_INCREASING,
            measurement_to_ha=lambda x: x / 1000,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            ThirdRealityMeteringCluster.Attributes.CurrentSummationDelivered,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="NeoEnergySensorWatt",
            device_class=SensorDeviceClass.POWER,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
            measurement_to_ha=lambda x: x / 10,
        ),
        entity_class=MatterSensor,
        required_attributes=(NeoCluster.Attributes.Watt,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="NeoEnergySensorWattAccumulated",
            device_class=SensorDeviceClass.ENERGY,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            suggested_display_precision=1,
            state_class=SensorStateClass.TOTAL_INCREASING,
        ),
        entity_class=MatterSensor,
        required_attributes=(NeoCluster.Attributes.WattAccumulated,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="NeoEnergySensorVoltage",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
            measurement_to_ha=lambda x: x / 10,
        ),
        entity_class=MatterSensor,
        required_attributes=(NeoCluster.Attributes.Voltage,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="NeoEnergySensorWattCurrent",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(NeoCluster.Attributes.Current,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="SwitchCurrentPosition",
            native_unit_of_measurement=None,
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
            translation_key="switch_current_position",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.Switch.Attributes.CurrentPosition,),
        allow_multi=True,  # also used for event entity
    ),
]
