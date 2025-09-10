"""Matter sensors."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterAttributeDescriptor
from chip.clusters.Types import Nullable, NullValue
from matter_server.client.models import device_types
from matter_server.common.custom_clusters import (
    DraftElectricalMeasurementCluster,
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
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    Platform,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util, slugify

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

EVE_CLUSTER_WEATHER_MAP = {
    # enum with known Weather state values which we can translate
    1: "sunny",
    3: "cloudy",
    6: "rainy",
    14: "stormy",
}

OPERATIONAL_STATE_MAP = {
    # enum with known Operation state values which we can translate
    clusters.OperationalState.Enums.OperationalStateEnum.kStopped: "stopped",
    clusters.OperationalState.Enums.OperationalStateEnum.kRunning: "running",
    clusters.OperationalState.Enums.OperationalStateEnum.kPaused: "paused",
    clusters.OperationalState.Enums.OperationalStateEnum.kError: "error",
}

RVC_OPERATIONAL_STATE_MAP = {
    # enum with known Operation state values which we can translate
    **OPERATIONAL_STATE_MAP,
    clusters.RvcOperationalState.Enums.OperationalStateEnum.kSeekingCharger: "seeking_charger",
    clusters.RvcOperationalState.Enums.OperationalStateEnum.kCharging: "charging",
    clusters.RvcOperationalState.Enums.OperationalStateEnum.kDocked: "docked",
}

BOOST_STATE_MAP = {
    clusters.WaterHeaterManagement.Enums.BoostStateEnum.kInactive: "inactive",
    clusters.WaterHeaterManagement.Enums.BoostStateEnum.kActive: "active",
    clusters.WaterHeaterManagement.Enums.BoostStateEnum.kUnknownEnumValue: None,
}

CHARGE_STATE_MAP = {
    clusters.PowerSource.Enums.BatChargeStateEnum.kUnknown: None,
    clusters.PowerSource.Enums.BatChargeStateEnum.kIsNotCharging: "not_charging",
    clusters.PowerSource.Enums.BatChargeStateEnum.kIsCharging: "charging",
    clusters.PowerSource.Enums.BatChargeStateEnum.kIsAtFullCharge: "full_charge",
    clusters.PowerSource.Enums.BatChargeStateEnum.kUnknownEnumValue: None,
}

DEM_OPT_OUT_STATE_MAP = {
    clusters.DeviceEnergyManagement.Enums.OptOutStateEnum.kNoOptOut: "no_opt_out",
    clusters.DeviceEnergyManagement.Enums.OptOutStateEnum.kLocalOptOut: "local_opt_out",
    clusters.DeviceEnergyManagement.Enums.OptOutStateEnum.kGridOptOut: "grid_opt_out",
    clusters.DeviceEnergyManagement.Enums.OptOutStateEnum.kOptOut: "opt_out",
}

ESA_STATE_MAP = {
    clusters.DeviceEnergyManagement.Enums.ESAStateEnum.kOffline: "offline",
    clusters.DeviceEnergyManagement.Enums.ESAStateEnum.kOnline: "online",
    clusters.DeviceEnergyManagement.Enums.ESAStateEnum.kFault: "fault",
    clusters.DeviceEnergyManagement.Enums.ESAStateEnum.kPowerAdjustActive: "power_adjust_active",
    clusters.DeviceEnergyManagement.Enums.ESAStateEnum.kPaused: "paused",
}

EVSE_FAULT_STATE_MAP = {
    clusters.EnergyEvse.Enums.FaultStateEnum.kNoError: "no_error",
    clusters.EnergyEvse.Enums.FaultStateEnum.kMeterFailure: "meter_failure",
    clusters.EnergyEvse.Enums.FaultStateEnum.kOverVoltage: "over_voltage",
    clusters.EnergyEvse.Enums.FaultStateEnum.kUnderVoltage: "under_voltage",
    clusters.EnergyEvse.Enums.FaultStateEnum.kOverCurrent: "over_current",
    clusters.EnergyEvse.Enums.FaultStateEnum.kContactWetFailure: "contact_wet_failure",
    clusters.EnergyEvse.Enums.FaultStateEnum.kContactDryFailure: "contact_dry_failure",
    clusters.EnergyEvse.Enums.FaultStateEnum.kPowerLoss: "power_loss",
    clusters.EnergyEvse.Enums.FaultStateEnum.kPowerQuality: "power_quality",
    clusters.EnergyEvse.Enums.FaultStateEnum.kPilotShortCircuit: "pilot_short_circuit",
    clusters.EnergyEvse.Enums.FaultStateEnum.kEmergencyStop: "emergency_stop",
    clusters.EnergyEvse.Enums.FaultStateEnum.kEVDisconnected: "ev_disconnected",
    clusters.EnergyEvse.Enums.FaultStateEnum.kWrongPowerSupply: "wrong_power_supply",
    clusters.EnergyEvse.Enums.FaultStateEnum.kLiveNeutralSwap: "live_neutral_swap",
    clusters.EnergyEvse.Enums.FaultStateEnum.kOverTemperature: "over_temperature",
    clusters.EnergyEvse.Enums.FaultStateEnum.kOther: "other",
}

PUMP_CONTROL_MODE_MAP = {
    clusters.PumpConfigurationAndControl.Enums.ControlModeEnum.kConstantSpeed: "constant_speed",
    clusters.PumpConfigurationAndControl.Enums.ControlModeEnum.kConstantPressure: "constant_pressure",
    clusters.PumpConfigurationAndControl.Enums.ControlModeEnum.kProportionalPressure: "proportional_pressure",
    clusters.PumpConfigurationAndControl.Enums.ControlModeEnum.kConstantFlow: "constant_flow",
    clusters.PumpConfigurationAndControl.Enums.ControlModeEnum.kConstantTemperature: "constant_temperature",
    clusters.PumpConfigurationAndControl.Enums.ControlModeEnum.kAutomatic: "automatic",
    clusters.PumpConfigurationAndControl.Enums.ControlModeEnum.kUnknownEnumValue: None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter sensors from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.SENSOR, async_add_entities)


@dataclass(frozen=True)
class MatterSensorEntityDescription(SensorEntityDescription, MatterEntityDescription):
    """Describe Matter sensor entities."""


@dataclass(frozen=True, kw_only=True)
class MatterListSensorEntityDescription(MatterSensorEntityDescription):
    """Describe Matter sensor entities from MatterListSensor."""

    # list attribute: the attribute descriptor to get the list of values (= list of strings)
    list_attribute: type[ClusterAttributeDescriptor]


@dataclass(frozen=True, kw_only=True)
class MatterOperationalStateSensorEntityDescription(MatterSensorEntityDescription):
    """Describe Matter sensor entities from Matter OperationalState objects."""

    # list attribute: the attribute descriptor to get the list of values (= list of structs)
    # needs to be set for handling OperationalState not on the OperationalState cluster, but
    # on one of its derived clusters (e.g. RvcOperationalState)
    state_list_attribute: type[ClusterAttributeDescriptor] = (
        clusters.OperationalState.Attributes.OperationalStateList
    )
    state_attribute: type[ClusterAttributeDescriptor] = (
        clusters.OperationalState.Attributes.OperationalState
    )
    state_map: dict[int, str] = field(default_factory=lambda: OPERATIONAL_STATE_MAP)


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
        elif value_convert := self.entity_description.device_to_ha:
            value = value_convert(value)
        self._attr_native_value = value


class MatterDraftElectricalMeasurementSensor(MatterEntity, SensorEntity):
    """Representation of a Matter sensor for Matter 1.0 draft ElectricalMeasurement cluster."""

    entity_description: MatterSensorEntityDescription

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        raw_value: Nullable | float | None
        divisor: Nullable | float | None
        multiplier: Nullable | float | None

        raw_value, divisor, multiplier = (
            self.get_matter_attribute_value(self._entity_info.attributes_to_watch[0]),
            self.get_matter_attribute_value(self._entity_info.attributes_to_watch[1]),
            self.get_matter_attribute_value(self._entity_info.attributes_to_watch[2]),
        )

        for value in (divisor, multiplier):
            if value in (None, NullValue, 0):
                self._attr_native_value = None
                return

        if raw_value in (None, NullValue):
            self._attr_native_value = None
        else:
            self._attr_native_value = round(raw_value / divisor * multiplier, 2)


class MatterOperationalStateSensor(MatterSensor):
    """Representation of a sensor for Matter Operational State."""

    entity_description: MatterOperationalStateSensorEntityDescription
    states_map: dict[int, str]

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        # the operational state list is a list of the possible operational states
        # this is a dynamic list and is condition, device and manufacturer specific
        # therefore it is not possible to provide a fixed list of options
        # or to provide a mapping to a translateable string for all options
        operational_state_list = self.get_matter_attribute_value(
            self.entity_description.state_list_attribute
        )
        if TYPE_CHECKING:
            operational_state_list = cast(
                # cast to the generic OperationalStateStruct type just to help typing
                list[clusters.OperationalState.Structs.OperationalStateStruct],
                operational_state_list,
            )
        states_map: dict[int, str] = {}
        for state in operational_state_list:
            # prefer translateable (known) state from mapping,
            # fallback to the raw state label as given by the device/manufacturer
            states_map[state.operationalStateID] = (
                self.entity_description.state_map.get(
                    state.operationalStateID, slugify(state.operationalStateLabel)
                )
            )
        self.states_map = states_map
        self._attr_options = list(states_map.values())
        self._attr_native_value = states_map.get(
            self.get_matter_attribute_value(self.entity_description.state_attribute)
        )


class MatterListSensor(MatterSensor):
    """Representation of a sensor entity from Matter list from Cluster attribute(s)."""

    entity_description: MatterListSensorEntityDescription
    _attr_device_class = SensorDeviceClass.ENUM

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._attr_options = list_values = cast(
            list[str],
            self.get_matter_attribute_value(self.entity_description.list_attribute),
        )
        current_value: int = self.get_matter_attribute_value(
            self._entity_info.primary_attribute
        )
        try:
            self._attr_native_value = list_values[current_value]
        except IndexError:
            self._attr_native_value = None


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="TemperatureSensor",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            device_to_ha=lambda x: x / 100,
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
            device_to_ha=lambda x: x / 10,
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
            device_to_ha=lambda x: x / 10,
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
            device_to_ha=lambda x: x / 100,
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
            device_to_ha=lambda x: round(pow(10, ((x - 1) / 10000)), 1),
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
            device_to_ha=lambda x: int(x / 2),
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.PowerSource.Attributes.BatPercentRemaining,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PowerSourceBatVoltage",
            translation_key="battery_voltage",
            native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.PowerSource.Attributes.BatVoltage,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PowerSourceBatTimeRemaining",
            translation_key="battery_time_remaining",
            native_unit_of_measurement=UnitOfTime.SECONDS,
            suggested_unit_of_measurement=UnitOfTime.MINUTES,
            device_class=SensorDeviceClass.DURATION,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.PowerSource.Attributes.BatTimeRemaining,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PowerSourceBatChargeState",
            translation_key="battery_charge_state",
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            options=[state for state in CHARGE_STATE_MAP.values() if state is not None],
            device_to_ha=CHARGE_STATE_MAP.get,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.PowerSource.Attributes.BatChargeState,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PowerSourceBatTimeToFullCharge",
            translation_key="battery_time_to_full_charge",
            native_unit_of_measurement=UnitOfTime.SECONDS,
            suggested_unit_of_measurement=UnitOfTime.MINUTES,
            device_class=SensorDeviceClass.DURATION,
            entity_category=EntityCategory.DIAGNOSTIC,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.PowerSource.Attributes.BatTimeToFullCharge,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PowerSourceBatReplacementDescription",
            translation_key="battery_replacement_description",
            native_unit_of_measurement=None,
            device_class=None,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.PowerSource.Attributes.BatReplacementDescription,
        ),
        # Some manufacturers returns an empty string
        value_is_not="",
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
            key="EveWeatherWeatherTrend",
            translation_key="eve_weather_trend",
            device_class=SensorDeviceClass.ENUM,
            native_unit_of_measurement=None,
            options=[x for x in EVE_CLUSTER_WEATHER_MAP.values() if x is not None],
            device_to_ha=EVE_CLUSTER_WEATHER_MAP.get,
        ),
        entity_class=MatterSensor,
        required_attributes=(EveCluster.Attributes.WeatherTrend,),
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
            device_to_ha=lambda x: AIR_QUALITY_MAP[x],
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
            translation_key="nitrogen_dioxide",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
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
            device_to_ha=lambda x: x / 1000,
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
            device_to_ha=lambda x: x / 1000,
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
            device_to_ha=lambda x: x / 10,
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
            device_to_ha=lambda x: x / 10,
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
            native_unit_of_measurement=UnitOfPower.MILLIWATT,
            suggested_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.ActivePower,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementApparentPower",
            device_class=SensorDeviceClass.APPARENT_POWER,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfApparentPower.MILLIVOLT_AMPERE,
            suggested_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.ApparentPower,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementReactivePower",
            device_class=SensorDeviceClass.REACTIVE_POWER,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfReactivePower.MILLIVOLT_AMPERE_REACTIVE,
            suggested_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.ReactivePower,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementVoltage",
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.ElectricalPowerMeasurement.Attributes.Voltage,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementRMSVoltage",
            translation_key="rms_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.RMSVoltage,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementApparentCurrent",
            translation_key="apparent_current",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.ApparentCurrent,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementActiveCurrent",
            translation_key="active_current",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.ActiveCurrent,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementReactiveCurrent",
            translation_key="reactive_current",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.ReactiveCurrent,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalPowerMeasurementRMSCurrent",
            translation_key="rms_current",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalPowerMeasurement.Attributes.RMSCurrent,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalEnergyMeasurementCumulativeEnergyImported",
            device_class=SensorDeviceClass.ENERGY,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfEnergy.MILLIWATT_HOUR,
            suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=3,
            state_class=SensorStateClass.TOTAL_INCREASING,
            # id 0 of the EnergyMeasurementStruct is the cumulative energy (in mWh)
            device_to_ha=lambda x: x.energy,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalEnergyMeasurement.Attributes.CumulativeEnergyImported,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalEnergyMeasurementCumulativeEnergyExported",
            translation_key="energy_exported",
            device_class=SensorDeviceClass.ENERGY,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfEnergy.MILLIWATT_HOUR,
            suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=3,
            state_class=SensorStateClass.TOTAL_INCREASING,
            # id 0 of the EnergyMeasurementStruct is the cumulative energy (in mWh)
            device_to_ha=lambda x: x.energy,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.ElectricalEnergyMeasurement.Attributes.CumulativeEnergyExported,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalMeasurementActivePower",
            device_class=SensorDeviceClass.POWER,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterDraftElectricalMeasurementSensor,
        required_attributes=(
            DraftElectricalMeasurementCluster.Attributes.ActivePower,
            DraftElectricalMeasurementCluster.Attributes.AcPowerDivisor,
            DraftElectricalMeasurementCluster.Attributes.AcPowerMultiplier,
        ),
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalMeasurementRmsVoltage",
            device_class=SensorDeviceClass.VOLTAGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=0,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterDraftElectricalMeasurementSensor,
        required_attributes=(
            DraftElectricalMeasurementCluster.Attributes.RmsVoltage,
            DraftElectricalMeasurementCluster.Attributes.AcVoltageDivisor,
            DraftElectricalMeasurementCluster.Attributes.AcVoltageMultiplier,
        ),
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ElectricalMeasurementRmsCurrent",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterDraftElectricalMeasurementSensor,
        required_attributes=(
            DraftElectricalMeasurementCluster.Attributes.RmsCurrent,
            DraftElectricalMeasurementCluster.Attributes.AcCurrentDivisor,
            DraftElectricalMeasurementCluster.Attributes.AcCurrentMultiplier,
        ),
        absent_clusters=(clusters.ElectricalPowerMeasurement,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="SmokeCOAlarmContaminationState",
            translation_key="contamination_state",
            device_class=SensorDeviceClass.ENUM,
            options=list(CONTAMINATION_STATE_MAP.values()),
            device_to_ha=CONTAMINATION_STATE_MAP.get,
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
            device_to_ha=datetime.fromtimestamp,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.SmokeCoAlarm.Attributes.ExpiryDate,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterOperationalStateSensorEntityDescription(
            key="OperationalState",
            device_class=SensorDeviceClass.ENUM,
            translation_key="operational_state",
        ),
        entity_class=MatterOperationalStateSensor,
        required_attributes=(
            clusters.OperationalState.Attributes.OperationalState,
            clusters.OperationalState.Attributes.OperationalStateList,
        ),
        # don't discover this entry if the supported state list is empty
        secondary_value_is_not=[],
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="OperationalStateCountdownTime",
            translation_key="estimated_end_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            state_class=None,
            # Add countdown to current datetime to get the estimated end time
            device_to_ha=(
                lambda x: dt_util.utcnow() + timedelta(seconds=x) if x > 0 else None
            ),
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.OperationalState.Attributes.CountdownTime,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterListSensorEntityDescription(
            key="OperationalStateCurrentPhase",
            translation_key="current_phase",
            list_attribute=clusters.OperationalState.Attributes.PhaseList,
        ),
        entity_class=MatterListSensor,
        required_attributes=(
            clusters.OperationalState.Attributes.CurrentPhase,
            clusters.OperationalState.Attributes.PhaseList,
        ),
        # don't discover this entry if the supported state list is empty
        secondary_value_is_not=[],
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterListSensorEntityDescription(
            key="RvcOperationalStateCurrentPhase",
            translation_key="current_phase",
            list_attribute=clusters.RvcOperationalState.Attributes.PhaseList,
        ),
        entity_class=MatterListSensor,
        required_attributes=(
            clusters.RvcOperationalState.Attributes.CurrentPhase,
            clusters.RvcOperationalState.Attributes.PhaseList,
        ),
        # don't discover this entry if the supported state list is empty
        secondary_value_is_not=[],
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterListSensorEntityDescription(
            key="OvenCavityOperationalStateCurrentPhase",
            translation_key="current_phase",
            list_attribute=clusters.OvenCavityOperationalState.Attributes.PhaseList,
        ),
        entity_class=MatterListSensor,
        required_attributes=(
            clusters.OvenCavityOperationalState.Attributes.CurrentPhase,
            clusters.OvenCavityOperationalState.Attributes.PhaseList,
        ),
        # don't discover this entry if the supported state list is empty
        secondary_value_is_not=[],
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ThermostatLocalTemperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            device_to_ha=lambda x: x / 100,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.Thermostat.Attributes.LocalTemperature,),
        device_type=(device_types.Thermostat,),
        allow_multi=True,  # also used for climate entity
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterOperationalStateSensorEntityDescription(
            key="RvcOperationalState",
            device_class=SensorDeviceClass.ENUM,
            translation_key="operational_state",
            state_list_attribute=clusters.RvcOperationalState.Attributes.OperationalStateList,
            state_attribute=clusters.RvcOperationalState.Attributes.OperationalState,
            state_map=RVC_OPERATIONAL_STATE_MAP,
        ),
        entity_class=MatterOperationalStateSensor,
        required_attributes=(
            clusters.RvcOperationalState.Attributes.OperationalState,
            clusters.RvcOperationalState.Attributes.OperationalStateList,
        ),
        allow_multi=True,  # also used for vacuum entity
        # don't discover this entry if the supported state list is empty
        secondary_value_is_not=[],
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterOperationalStateSensorEntityDescription(
            key="OvenCavityOperationalState",
            device_class=SensorDeviceClass.ENUM,
            translation_key="operational_state",
            state_list_attribute=clusters.OvenCavityOperationalState.Attributes.OperationalStateList,
            state_attribute=clusters.OvenCavityOperationalState.Attributes.OperationalState,
        ),
        entity_class=MatterOperationalStateSensor,
        required_attributes=(
            clusters.OvenCavityOperationalState.Attributes.OperationalState,
            clusters.OvenCavityOperationalState.Attributes.OperationalStateList,
        ),
        # don't discover this entry if the supported state list is empty
        secondary_value_is_not=[],
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="TargetPositionLiftPercent100ths",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            translation_key="window_covering_target_position",
            device_to_ha=lambda x: round((10000 - x) / 100),
            native_unit_of_measurement=PERCENTAGE,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.WindowCovering.Attributes.TargetPositionLiftPercent100ths,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EnergyEvseFaultState",
            translation_key="evse_fault_state",
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            options=list(EVSE_FAULT_STATE_MAP.values()),
            device_to_ha=EVSE_FAULT_STATE_MAP.get,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.EnergyEvse.Attributes.FaultState,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EnergyEvseCircuitCapacity",
            translation_key="evse_circuit_capacity",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.EnergyEvse.Attributes.CircuitCapacity,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EnergyEvseMinimumChargeCurrent",
            translation_key="evse_min_charge_current",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.EnergyEvse.Attributes.MinimumChargeCurrent,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EnergyEvseMaximumChargeCurrent",
            translation_key="evse_max_charge_current",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.EnergyEvse.Attributes.MaximumChargeCurrent,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EnergyEvseUserMaximumChargeCurrent",
            translation_key="evse_user_max_charge_current",
            device_class=SensorDeviceClass.CURRENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            suggested_display_precision=2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.EnergyEvse.Attributes.UserMaximumChargeCurrent,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="EnergyEvseStateOfCharge",
            translation_key="evse_soc",
            native_unit_of_measurement=PERCENTAGE,
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.EnergyEvse.Attributes.StateOfCharge,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="WaterHeaterManagementTankVolume",
            translation_key="tank_volume",
            device_class=SensorDeviceClass.VOLUME_STORAGE,
            native_unit_of_measurement=UnitOfVolume.LITERS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.WaterHeaterManagement.Attributes.TankVolume,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="WaterHeaterManagementTankPercentage",
            translation_key="tank_percentage",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.WaterHeaterManagement.Attributes.TankPercentage,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="WaterHeaterManagementEstimatedHeatRequired",
            translation_key="estimated_heat_required",
            device_class=SensorDeviceClass.ENERGY,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_unit_of_measurement=UnitOfEnergy.MILLIWATT_HOUR,
            suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            suggested_display_precision=3,
            state_class=SensorStateClass.TOTAL,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.WaterHeaterManagement.Attributes.EstimatedHeatRequired,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ESAState",
            translation_key="esa_state",
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            options=list(ESA_STATE_MAP.values()),
            device_to_ha=ESA_STATE_MAP.get,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.DeviceEnergyManagement.Attributes.ESAState,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ESAOptOutState",
            translation_key="esa_opt_out_state",
            device_class=SensorDeviceClass.ENUM,
            entity_category=EntityCategory.DIAGNOSTIC,
            options=list(DEM_OPT_OUT_STATE_MAP.values()),
            device_to_ha=DEM_OPT_OUT_STATE_MAP.get,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.DeviceEnergyManagement.Attributes.OptOutState,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PumpControlMode",
            translation_key="pump_control_mode",
            device_class=SensorDeviceClass.ENUM,
            options=[
                mode for mode in PUMP_CONTROL_MODE_MAP.values() if mode is not None
            ],
            device_to_ha=PUMP_CONTROL_MODE_MAP.get,
        ),
        entity_class=MatterSensor,
        required_attributes=(
            clusters.PumpConfigurationAndControl.Attributes.ControlMode,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="PumpSpeed",
            translation_key="pump_speed",
            native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        entity_class=MatterSensor,
        required_attributes=(clusters.PumpConfigurationAndControl.Attributes.Speed,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SENSOR,
        entity_description=MatterSensorEntityDescription(
            key="ValveConfigurationAndControlAutoCloseTime",
            translation_key="auto_close_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            state_class=None,
            device_to_ha=(lambda x: dt_util.utc_from_timestamp(x) if x > 0 else None),
        ),
        entity_class=MatterSensor,
        featuremap_contains=clusters.ValveConfigurationAndControl.Bitmaps.Feature.kTimeSync,
        required_attributes=(
            clusters.ValveConfigurationAndControl.Attributes.AutoCloseTime,
        ),
    ),
]
