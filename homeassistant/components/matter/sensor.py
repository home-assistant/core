"""Matter sensors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast

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
from homeassistant.util import slugify

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
    clusters.AirQuality.Enums.AirQualityEnum.kUnknown: None,
    clusters.AirQuality.Enums.AirQualityEnum.kUnknownEnumValue: None,
}

CONTAMINATION_STATE_MAP = {
    clusters.SmokeCoAlarm.Enums.ContaminationStateEnum.kNormal: "normal",
    clusters.SmokeCoAlarm.Enums.ContaminationStateEnum.kLow: "low",
    clusters.SmokeCoAlarm.Enums.ContaminationStateEnum.kWarning: "warning",
    clusters.SmokeCoAlarm.Enums.ContaminationStateEnum.kCritical: "critical",
}


OPERATIONAL_STATE_MAP = {
    # enum with known Operation state values which we can translate
    clusters.OperationalState.Enums.OperationalStateEnum.kStopped: "stopped",
    clusters.OperationalState.Enums.OperationalStateEnum.kRunning: "running",
    clusters.OperationalState.Enums.OperationalStateEnum.kPaused: "paused",
    clusters.OperationalState.Enums.OperationalStateEnum.kError: "error",
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


class MatterOperationalStateSensor(MatterSensor):
    """Representation of a sensor for Matter Operational State."""

    states_map: dict[int, str]

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        # the operational state list is a list of the possible operational states
        # this is a dynamic list and is condition, device and manufacturer specific
        # therefore it is not possible to provide a fixed list of options
        # or to provide a mapping to a translateable string for all options
        operational_state_list = self.get_matter_attribute_value(
            clusters.OperationalState.Attributes.OperationalStateList
        )
        if TYPE_CHECKING:
            operational_state_list = cast(
                list[clusters.OperationalState.Structs.OperationalStateStruct],
                operational_state_list,
            )
        states_map: dict[int, str] = {}
        for state in operational_state_list:
            # prefer translateable (known) state from mapping,
            # fallback to the raw state label as given by the device/manufacturer
            states_map[state.operationalStateID] = OPERATIONAL_STATE_MAP.get(
                state.operationalStateID, slugify(state.operationalStateLabel)
            )
        self.states_map = states_map
        self._attr_options = list(states_map.values())
        self._attr_native_value = states_map.get(
            self.get_matter_attribute_value(
                clusters.OperationalState.Attributes.OperationalState
            )
        )


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
            key="PowerSourceBatVoltage",
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            measurement_to_ha=lambda x: x / 1000,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.PowerSource.Attributes.BatVoltage,),
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
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
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
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
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
        absent_clusters=(clusters.ElectricalEnergyMeasurement,),
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
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EveThermoValvePosition",
            translation_key="valve_position",
            native_unit_of_measurement=PERCENTAGE,
        ),
        entity_class=MatterSensor,
        required_attributes=(EveCluster.Attributes.ValvePosition,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EveWeatherPressure",
            device_class=SensorDeviceClass.PRESSURE,
            native_unit_of_measurement=UnitOfPressure.HPA,
            suggested_display_precision=1,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(EveCluster.Attributes.Pressure,),
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
            options=[x for x in AIR_QUALITY_MAP.values() if x is not None],
            measurement_to_ha=lambda x: AIR_QUALITY_MAP[x],
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
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
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
        absent_clusters=(clusters.ElectricalEnergyMeasurement,),
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
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
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
        absent_clusters=(clusters.ElectricalEnergyMeasurement,),
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
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
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
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
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
            entity_registry_enabled_default=False,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.Switch.Attributes.CurrentPosition,),
        allow_multi=True,  # also used for event entity
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementWatt",
            device_class=SensorDeviceClass.POWER,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
            measurement_to_ha=lambda x: x / 1000,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.ActivePower,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementVoltage",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
            measurement_to_ha=lambda x: x / 1000,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.ElectricalPowerMeasurement.Attributes.Voltage,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementActiveCurrent",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
            measurement_to_ha=lambda x: x / 1000,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.ActiveCurrent,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalEnergyMeasurementCumulativeEnergyImported",
            device_class=SensorDeviceClass.ENERGY,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=3,
            state_class=SensorStateClass.TOTAL_INCREASING,
            # id 0 of the EnergyMeasurementStruct is the cumulative energy (in mWh)
            measurement_to_ha=lambda x: x.energy / 1000000,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalEnergyMeasurement.Attributes.CumulativeEnergyImported,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="SmokeCOAlarmContaminationState",
            translation_key="contamination_state",
            device_class=SensorDeviceClass.ENUM,
            options=list(CONTAMINATION_STATE_MAP.values()),
            measurement_to_ha=CONTAMINATION_STATE_MAP.get,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.ContaminationState,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="SmokeCOAlarmExpiryDate",
            translation_key="expiry_date",
            device_class=SensorDeviceClass.TIMESTAMP,
            # raw value is epoch seconds
            measurement_to_ha=datetime.fromtimestamp,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.ExpiryDate,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="OperationalState",
            device_class=SensorDeviceClass.ENUM,
            translation_key="operational_state",
        ),
        entity_class=MatterOperationalStateSensor,
        required_attributes=(
            clusters.OperationalState.Attributes.OperationalState,
            clusters.OperationalState.Attributes.OperationalStateList,
        ),
    ),
]
