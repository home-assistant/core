"""Constants and shared entity descriptions for Daikin Onecta."""

from dataclasses import dataclass
from typing import Any, NamedTuple

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.climate import ClimateEntityDescription
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.update import UpdateDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDensity,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)

DOMAIN = "daikin_onecta"

OAUTH2_AUTHORIZE = "https://idp.onecta.daikineurope.com/v1/oidc/authorize"
OAUTH2_TOKEN = "https://idp.onecta.daikineurope.com/v1/oidc/token"

FANMODE_FIXED = "fixed"


class EnergyPeriod(NamedTuple):
    """Home Assistant labels and ID suffixes for Daikin energy periods."""

    label: str
    unique_id_suffix: str


ENERGY_AGGREGATE_PERIODS: dict[str, EnergyPeriod] = {
    "day": EnergyPeriod("Daily", "daily"),
    "week": EnergyPeriod("Weekly", "weekly"),
    "year": EnergyPeriod("Yearly", "yearly"),
    "month": EnergyPeriod("Monthly", "monthly"),
}

CLIMATE_ENTITY_DESCRIPTIONS: dict[str, ClimateEntityDescription] = {
    "calculatedLeavingWaterTemperature": ClimateEntityDescription(
        key="calculated_leaving_water_temperature",
        translation_key="calculated_leaving_water_temperature",
    ),
    "leavingWaterOffset": ClimateEntityDescription(
        key="leaving_water_offset",
        translation_key="leaving_water_offset",
    ),
    "leavingWaterTemperature": ClimateEntityDescription(
        key="leaving_water_temperature",
        translation_key="leaving_water_temperature",
    ),
    "roomTemperature": ClimateEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
    ),
}

CLIMATE_SETPOINT_TYPES = frozenset(CLIMATE_ENTITY_DESCRIPTIONS)


@dataclass(frozen=True, kw_only=True)
class DaikinEntityMetadata:
    """Typed metadata used to build platform-specific entity descriptions."""

    key: str
    device_class: SensorDeviceClass | BinarySensorDeviceClass | UpdateDeviceClass | None
    state_class: SensorStateClass | None
    native_unit_of_measurement: str | None
    entity_registry_enabled_default: bool
    entity_category: EntityCategory | None
    translation_key: str
    options: tuple[str, ...] | None = None


ENTITY_METADATA: tuple[DaikinEntityMetadata, ...] = (
    DaikinEntityMetadata(
        key="sgtin",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="sgtin",
    ),
    DaikinEntityMetadata(
        key="controlMode",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="controlmode",
        options=(
            "leaving_water_temperature",
            "external_room_temperature",
            "room_temperature",
        ),
    ),
    DaikinEntityMetadata(
        key="onOffMode",
        device_class=BinarySensorDeviceClass.POWER,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="onoffmode",
    ),
    DaikinEntityMetadata(
        key="operationMode",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="operationmode",
        options=(
            "fan_only",
            "heating",
            "cooling",
            "auto",
            "dry",
            "off",
            "heating_day",
            "heating_night",
            "humidification",
        ),
    ),
    DaikinEntityMetadata(
        key="airPurificationMode",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="airpurificationmode",
        options=(
            "manual_fan",
            "auto_fan",
            "econo",
            "anti_pollen",
            "circulator",
            "auto",
            "moist",
            "off",
        ),
    ),
    DaikinEntityMetadata(
        key="setpointMode",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="setpointmode",
        options=(
            "fixed",
            "weather_dependent",
            "weather_dependent_heating_fixed_cooling",
            "weather_dependent_cooling_fixed_heating",
        ),
    ),
    DaikinEntityMetadata(
        key="heatupMode",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatupmode",
        options=("reheat_only", "reheat_schedule", "schedule_only", "scheduled_reheat"),
    ),
    DaikinEntityMetadata(
        key="wifiConnectionSSID",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="wificonnectionssid",
    ),
    DaikinEntityMetadata(
        key="wifiConnectionStrength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="wificonnectionstrength",
    ),
    DaikinEntityMetadata(
        key="ssid",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="ssid",
    ),
    DaikinEntityMetadata(
        key="isHolidayModeActive",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="isholidaymodeactive",
    ),
    DaikinEntityMetadata(
        key="isInErrorState",
        device_class=BinarySensorDeviceClass.PROBLEM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="isinerrorstate",
    ),
    DaikinEntityMetadata(
        key="isInWarningState",
        device_class=BinarySensorDeviceClass.PROBLEM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="isinwarningstate",
    ),
    DaikinEntityMetadata(
        key="isInInstallerState",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="isininstallerstate",
    ),
    DaikinEntityMetadata(
        key="isInEmergencyState",
        device_class=BinarySensorDeviceClass.PROBLEM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="isinemergencystate",
    ),
    DaikinEntityMetadata(
        key="isPowerfulModeActive",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="ispowerfulmodeactive",
    ),
    DaikinEntityMetadata(
        key="isCoolHeatMaster",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="iscoolheatmaster",
    ),
    DaikinEntityMetadata(
        key="isInModeConflict",
        device_class=BinarySensorDeviceClass.PROBLEM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="isinmodeconflict",
    ),
    DaikinEntityMetadata(
        key="isInCautionState",
        device_class=BinarySensorDeviceClass.PROBLEM,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="isincautionstate",
    ),
    DaikinEntityMetadata(
        key="isLockFunctionEnabled",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="islockfunctionenabled",
    ),
    DaikinEntityMetadata(
        key="ledEnabled",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="ledenabled",
    ),
    DaikinEntityMetadata(
        key="isFirmwareUpdateSupported",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="isfirmwareupdatesupported",
    ),
    DaikinEntityMetadata(
        key="daylightSavingTimeEnabled",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="daylightsavingtimeenabled",
    ),
    DaikinEntityMetadata(
        key="roomTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="roomtemperature",
    ),
    DaikinEntityMetadata(
        key="outdoorTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="outdoortemperature",
    ),
    DaikinEntityMetadata(
        key="leavingWaterTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="leavingwatertemperature",
    ),
    DaikinEntityMetadata(
        key="leavingWaterOffset",
        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="leavingwateroffset",
    ),
    DaikinEntityMetadata(
        key="calculatedLeavingWaterTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="calculatedleavingwatertemperature",
    ),
    DaikinEntityMetadata(
        key="tankTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="tanktemperature",
    ),
    DaikinEntityMetadata(
        key="heatExchangerTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatexchangertemperature",
    ),
    DaikinEntityMetadata(
        key="suctionTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="suctiontemperature",
    ),
    DaikinEntityMetadata(
        key="deltaD",
        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="deltad",
    ),
    DaikinEntityMetadata(
        key="dryKeepSetting",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="drykeepsetting",
    ),
    DaikinEntityMetadata(
        key="streamerMode",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="streamermode",
    ),
    DaikinEntityMetadata(
        key="powerfulMode",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="powerfulmode",
    ),
    DaikinEntityMetadata(
        key="econoMode",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="economode",
    ),
    DaikinEntityMetadata(
        key="fanMotorRotationSpeed",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="fanmotorrotationspeed",
    ),
    DaikinEntityMetadata(
        key="ipAddress",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="ipaddress",
    ),
    DaikinEntityMetadata(
        key="dateTime",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="datetime",
    ),
    DaikinEntityMetadata(
        key="regionCode",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="regioncode",
    ),
    DaikinEntityMetadata(
        key="errorCode",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="errorcode",
    ),
    DaikinEntityMetadata(
        key="timeZone",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="timezone",
    ),
    DaikinEntityMetadata(
        key="roomHumidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="roomhumidity",
    ),
    DaikinEntityMetadata(
        key="pm1Concentration",
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="pm1concentration",
    ),
    DaikinEntityMetadata(
        key="pm25Concentration",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="pm25concentration",
    ),
    DaikinEntityMetadata(
        key="pm10Concentration",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="pm10concentration",
    ),
    DaikinEntityMetadata(
        key="CoolingDailyElectricalConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingdailyelectricalconsumption",
    ),
    DaikinEntityMetadata(
        key="CoolingWeeklyElectricalConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingweeklyelectricalconsumption",
    ),
    DaikinEntityMetadata(
        key="CoolingMonthlyElectricalConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingmonthlyelectricalconsumption",
    ),
    DaikinEntityMetadata(
        key="CoolingYearlyElectricalConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingyearlyelectricalconsumption",
    ),
    DaikinEntityMetadata(
        key="HeatingDailyElectricalConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingdailyelectricalconsumption",
    ),
    DaikinEntityMetadata(
        key="HeatingWeeklyElectricalConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingweeklyelectricalconsumption",
    ),
    DaikinEntityMetadata(
        key="HeatingMonthlyElectricalConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingmonthlyelectricalconsumption",
    ),
    DaikinEntityMetadata(
        key="HeatingYearlyElectricalConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingyearlyelectricalconsumption",
    ),
    DaikinEntityMetadata(
        key="CoolingDailyGasConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingdailygasconsumption",
    ),
    DaikinEntityMetadata(
        key="CoolingWeeklyGasConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingweeklygasconsumption",
    ),
    DaikinEntityMetadata(
        key="CoolingMonthlyGasConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingmonthlygasconsumption",
    ),
    DaikinEntityMetadata(
        key="CoolingYearlyGasConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingyearlygasconsumption",
    ),
    DaikinEntityMetadata(
        key="HeatingDailyGasConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingdailygasconsumption",
    ),
    DaikinEntityMetadata(
        key="HeatingWeeklyGasConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingweeklygasconsumption",
    ),
    DaikinEntityMetadata(
        key="HeatingMonthlyGasConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingmonthlygasconsumption",
    ),
    DaikinEntityMetadata(
        key="HeatingYearlyGasConsumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingyearlygasconsumption",
    ),
    DaikinEntityMetadata(
        key="RatelimitRemainingDay",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="ratelimitremainingday",
    ),
    DaikinEntityMetadata(
        key="FirmwareUpdate",
        device_class=UpdateDeviceClass.FIRMWARE,
        state_class=None,
        native_unit_of_measurement=None,
        entity_registry_enabled_default=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="firmwareupdate",
    ),
    DaikinEntityMetadata(
        key="currentPowerConsumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="currentpowerconsumption",
    ),
    DaikinEntityMetadata(
        key="currentHeatProduction",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="currentthermaloutput",
    ),
    DaikinEntityMetadata(
        key="HeatingMonthlyThermalOutput",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingmonthlythermaloutput",
    ),
    DaikinEntityMetadata(
        key="HeatingYearlyThermalOutput",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="heatingyearlythermaloutput",
    ),
    DaikinEntityMetadata(
        key="CoolingMonthlyThermalOutput",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingmonthlythermaloutput",
    ),
    DaikinEntityMetadata(
        key="CoolingYearlyThermalOutput",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        entity_category=None,
        translation_key="coolingyearlythermaloutput",
    ),
)


def entity_description_kwargs(metadata: DaikinEntityMetadata) -> dict[str, Any]:
    """Return the entity-description fields shared by all platforms."""
    return {
        "translation_key": metadata.translation_key,
        "entity_category": metadata.entity_category,
        "entity_registry_enabled_default": metadata.entity_registry_enabled_default,
    }


BINARY_SENSOR_TRANSLATION_KEYS = frozenset(
    {
        "daylightsavingtimeenabled",
        "iscoolheatmaster",
        "isfirmwareupdatesupported",
        "isholidaymodeactive",
        "isincautionstate",
        "isinemergencystate",
        "isinerrorstate",
        "isininstallerstate",
        "isinmodeconflict",
        "isinwarningstate",
        "islockfunctionenabled",
        "ispowerfulmodeactive",
        "ledenabled",
        "onoffmode",
        "drykeepsetting",
    }
)
SWITCH_TRANSLATION_KEYS = frozenset({"economode", "onoffmode", "streamermode"})

BINARY_SENSOR_KEYS = frozenset(
    metadata.key
    for metadata in ENTITY_METADATA
    if metadata.translation_key in BINARY_SENSOR_TRANSLATION_KEYS
)
SWITCH_KEYS = frozenset(
    metadata.key
    for metadata in ENTITY_METADATA
    if metadata.translation_key in SWITCH_TRANSLATION_KEYS
)
UPDATE_KEYS = frozenset(
    metadata.key
    for metadata in ENTITY_METADATA
    if isinstance(metadata.device_class, UpdateDeviceClass)
)
SENSOR_KEYS = frozenset(metadata.key for metadata in ENTITY_METADATA) - (
    BINARY_SENSOR_KEYS | SWITCH_KEYS | UPDATE_KEYS
)
