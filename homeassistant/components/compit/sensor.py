"""Sensor platform for Compit integration."""

from dataclasses import dataclass

from compit_inext_api.consts import CompitParameter

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

PARALLEL_UPDATES = 0
NO_SENSOR = "no_sensor"

DESCRIPTIONS: dict[CompitParameter, SensorEntityDescription] = {
    CompitParameter.ACTUAL_BUFFER_TEMP: SensorEntityDescription(
        key=CompitParameter.ACTUAL_BUFFER_TEMP.value,
        translation_key="actual_buffer_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.ACTUAL_DHW_TEMP: SensorEntityDescription(
        key=CompitParameter.ACTUAL_DHW_TEMP.value,
        translation_key="actual_dhw_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.ACTUAL_HC1_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.ACTUAL_HC1_TEMPERATURE.value,
        translation_key="actual_hc_temperature_zone",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_placeholders={"zone": "1"},
    ),
    CompitParameter.ACTUAL_HC2_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.ACTUAL_HC2_TEMPERATURE.value,
        translation_key="actual_hc_temperature_zone",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_placeholders={"zone": "2"},
    ),
    CompitParameter.ACTUAL_HC3_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.ACTUAL_HC3_TEMPERATURE.value,
        translation_key="actual_hc_temperature_zone",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_placeholders={"zone": "3"},
    ),
    CompitParameter.ACTUAL_HC4_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.ACTUAL_HC4_TEMPERATURE.value,
        translation_key="actual_hc_temperature_zone",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_placeholders={"zone": "4"},
    ),
    CompitParameter.ACTUAL_UPPER_SOURCE_TEMP: SensorEntityDescription(
        key=CompitParameter.ACTUAL_UPPER_SOURCE_TEMP.value,
        translation_key="actual_upper_source_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.ALARM_CODE: SensorEntityDescription(
        key=CompitParameter.ALARM_CODE.value,
        translation_key="alarm_code",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            "no_alarm",
            "damaged_outdoor_temp",
            "damaged_return_temp",
            "no_battery",
            "discharged_battery",
            "low_battery_level",
            "battery_fault",
            "no_pump",
            "pump_fault",
            "internal_af",
            "no_power",
        ],
    ),
    CompitParameter.BATTERY_LEVEL: SensorEntityDescription(
        key=CompitParameter.BATTERY_LEVEL.value,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    CompitParameter.BOILER_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.BOILER_TEMPERATURE.value,
        translation_key="boiler_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.BUFFER_RETURN_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.BUFFER_RETURN_TEMPERATURE.value,
        translation_key="buffer_return_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.BUFFER_SET_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.BUFFER_SET_TEMPERATURE.value,
        translation_key="buffer_set_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.CALCULATED_BUFFER_TEMP: SensorEntityDescription(
        key=CompitParameter.CALCULATED_BUFFER_TEMP.value,
        translation_key="calculated_buffer_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.CALCULATED_DHW_TEMP: SensorEntityDescription(
        key=CompitParameter.CALCULATED_DHW_TEMP.value,
        translation_key="calculated_dhw_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.CALCULATED_HEATING_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.CALCULATED_HEATING_TEMPERATURE.value,
        translation_key="calculated_heating_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.CALCULATED_TARGET_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.CALCULATED_TARGET_TEMPERATURE.value,
        translation_key="calculated_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.CALCULATED_UPPER_SOURCE_TEMP: SensorEntityDescription(
        key=CompitParameter.CALCULATED_UPPER_SOURCE_TEMP.value,
        translation_key="calculated_upper_source_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.CHARGING_POWER: SensorEntityDescription(
        key=CompitParameter.CHARGING_POWER.value,
        translation_key="charging_power",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
    ),
    CompitParameter.CIRCUIT_TARGET_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.CIRCUIT_TARGET_TEMPERATURE.value,
        translation_key="circuit_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.CO2_LEVEL: SensorEntityDescription(
        key=CompitParameter.CO2_LEVEL.value,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    CompitParameter.CO2_PERCENT: SensorEntityDescription(
        key=CompitParameter.CO2_PERCENT.value,
        translation_key="co2_percent",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    CompitParameter.COLLECTOR_POWER: SensorEntityDescription(
        key=CompitParameter.COLLECTOR_POWER.value,
        translation_key="collector_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    CompitParameter.COLLECTOR_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.COLLECTOR_TEMPERATURE.value,
        translation_key="collector_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.DHW_MEASURED_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.DHW_MEASURED_TEMPERATURE.value,
        translation_key="dhw_measured_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.DHW_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.DHW_TEMPERATURE.value,
        translation_key="dhw_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.ENERGY_CONSUMPTION: SensorEntityDescription(
        key=CompitParameter.ENERGY_CONSUMPTION.value,
        translation_key="energy_consumption",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.MEGA_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    CompitParameter.ENERGY_SGREADY_YESTERDAY: SensorEntityDescription(
        key=CompitParameter.ENERGY_SGREADY_YESTERDAY.value,
        translation_key="energy_smart_grid_yesterday",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    CompitParameter.ENERGY_TODAY: SensorEntityDescription(
        key=CompitParameter.ENERGY_TODAY.value,
        translation_key="energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    CompitParameter.ENERGY_TOTAL: SensorEntityDescription(
        key=CompitParameter.ENERGY_TOTAL.value,
        translation_key="energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    CompitParameter.ENERGY_YESTERDAY: SensorEntityDescription(
        key=CompitParameter.ENERGY_YESTERDAY.value,
        translation_key="energy_yesterday",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    CompitParameter.FUEL_LEVEL: SensorEntityDescription(
        key=CompitParameter.FUEL_LEVEL.value,
        translation_key="fuel_level",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    CompitParameter.HEATING1_TARGET_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.HEATING1_TARGET_TEMPERATURE.value,
        translation_key="heating_target_temperature_zone",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_placeholders={"zone": "1"},
    ),
    CompitParameter.HEATING2_TARGET_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.HEATING2_TARGET_TEMPERATURE.value,
        translation_key="heating_target_temperature_zone",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_placeholders={"zone": "2"},
    ),
    CompitParameter.HEATING3_TARGET_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.HEATING3_TARGET_TEMPERATURE.value,
        translation_key="heating_target_temperature_zone",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_placeholders={"zone": "3"},
    ),
    CompitParameter.HEATING4_TARGET_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.HEATING4_TARGET_TEMPERATURE.value,
        translation_key="heating_target_temperature_zone",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_placeholders={"zone": "4"},
    ),
    CompitParameter.HUMIDITY: SensorEntityDescription(
        key=CompitParameter.HUMIDITY.value,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    CompitParameter.LOWER_SOURCE_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.LOWER_SOURCE_TEMPERATURE.value,
        translation_key="lower_source_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.MIXER_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.MIXER_TEMPERATURE.value,
        translation_key="mixer_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.MIXER1_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.MIXER1_TEMPERATURE.value,
        translation_key="mixer_temperature_zone",
        translation_placeholders={"zone": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.MIXER2_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.MIXER2_TEMPERATURE.value,
        translation_key="mixer_temperature_zone",
        translation_placeholders={"zone": "2"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.OUTDOOR_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.OUTDOOR_TEMPERATURE.value,
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.PK1_FUNCTION: SensorEntityDescription(
        key=CompitParameter.PK1_FUNCTION.value,
        translation_key="pk1_function",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            "off",
            "on",
            "nano_nr_1",
            "nano_nr_2",
            "nano_nr_3",
            "nano_nr_4",
            "nano_nr_5",
            "winter",
            "summer",
            "cooling",
            "holiday",
        ],
    ),
    CompitParameter.PM1_LEVEL_MEASURED: SensorEntityDescription(
        key=CompitParameter.PM1_LEVEL_MEASURED.value,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CompitParameter.PM4_LEVEL_MEASURED: SensorEntityDescription(
        key=CompitParameter.PM4_LEVEL_MEASURED.value,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.PM4,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CompitParameter.PM10_LEVEL: SensorEntityDescription(
        key=CompitParameter.PM10_LEVEL.value,
        translation_key="pm10_level",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=[NO_SENSOR, "normal", "warning", "exceeded"],
    ),
    CompitParameter.PM10_MEASURED: SensorEntityDescription(
        key=CompitParameter.PM10_MEASURED.value,
        device_class=SensorDeviceClass.PM10,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CompitParameter.PM25_LEVEL: SensorEntityDescription(
        key=CompitParameter.PM25_LEVEL.value,
        translation_key="pm25_level",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=[NO_SENSOR, "normal", "warning", "exceeded"],
    ),
    CompitParameter.PM25_MEASURED: SensorEntityDescription(
        key=CompitParameter.PM25_MEASURED.value,
        device_class=SensorDeviceClass.PM25,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    CompitParameter.PROTECTION_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.PROTECTION_TEMPERATURE.value,
        translation_key="protection_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.RETURN_CIRCUIT_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.RETURN_CIRCUIT_TEMPERATURE.value,
        translation_key="return_circuit_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.TANK_BOTTOM_T2_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.TANK_BOTTOM_T2_TEMPERATURE.value,
        translation_key="tank_temperature_t2",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.TANK_T4_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.TANK_T4_TEMPERATURE.value,
        translation_key="tank_temperature_t4",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_placeholders={"sensor": "T4"},
    ),
    CompitParameter.TANK_TOP_T3_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.TANK_TOP_T3_TEMPERATURE.value,
        translation_key="tank_temperature_t3",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.TARGET_HEATING_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.TARGET_HEATING_TEMPERATURE.value,
        translation_key="target_heating_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.UPPER_SOURCE_TEMPERATURE: SensorEntityDescription(
        key=CompitParameter.UPPER_SOURCE_TEMPERATURE.value,
        translation_key="upper_source_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CompitParameter.VENTILATION_ALARM: SensorEntityDescription(
        key=CompitParameter.VENTILATION_ALARM.value,
        translation_key="ventilation_alarm",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            "no_alarm",
            "damaged_supply_sensor",
            "damaged_exhaust_sensor",
            "damaged_supply_and_exhaust_sensors",
            "bot_alarm",
            "damaged_preheater_sensor",
            "ahu_alarm",
        ],
    ),
    CompitParameter.VENTILATION_GEAR: SensorEntityDescription(
        key=CompitParameter.VENTILATION_GEAR.value,
        translation_key="ventilation_gear",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


@dataclass(frozen=True, kw_only=True)
class CompitDeviceDescription:
    """Class to describe a Compit device."""

    name: str
    """Name of the device."""

    parameters: dict[CompitParameter, SensorEntityDescription]
    """Parameters of the device."""


DEVICE_DEFINITIONS: dict[int, CompitDeviceDescription] = {
    3: CompitDeviceDescription(
        name="R 810",
        parameters={
            CompitParameter.CALCULATED_HEATING_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.CALCULATED_HEATING_TEMPERATURE
            ],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
            CompitParameter.RETURN_CIRCUIT_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.RETURN_CIRCUIT_TEMPERATURE
            ],
            CompitParameter.TARGET_HEATING_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.TARGET_HEATING_TEMPERATURE
            ],
        },
    ),
    5: CompitDeviceDescription(
        name="R350 T3",
        parameters={
            CompitParameter.CALCULATED_TARGET_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.CALCULATED_TARGET_TEMPERATURE
            ],
            CompitParameter.CIRCUIT_TARGET_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.CIRCUIT_TARGET_TEMPERATURE
            ],
            CompitParameter.MIXER_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.MIXER_TEMPERATURE
            ],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    12: CompitDeviceDescription(
        name="Nano Color",
        parameters={
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
            CompitParameter.PM10_LEVEL: DESCRIPTIONS[CompitParameter.PM10_LEVEL],
            CompitParameter.PM25_LEVEL: DESCRIPTIONS[CompitParameter.PM25_LEVEL],
            CompitParameter.VENTILATION_ALARM: DESCRIPTIONS[
                CompitParameter.VENTILATION_ALARM
            ],
        },
    ),
    14: CompitDeviceDescription(
        name="BWC310",
        parameters={
            CompitParameter.CALCULATED_HEATING_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.CALCULATED_HEATING_TEMPERATURE
            ],
            CompitParameter.TARGET_HEATING_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.TARGET_HEATING_TEMPERATURE
            ],
        },
    ),
    27: CompitDeviceDescription(
        name="CO2 SHC",
        parameters={
            CompitParameter.HUMIDITY: DESCRIPTIONS[CompitParameter.HUMIDITY],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    34: CompitDeviceDescription(
        name="r470",
        parameters={
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    36: CompitDeviceDescription(
        name="BioMax742",
        parameters={
            CompitParameter.BOILER_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.BOILER_TEMPERATURE
            ],
            CompitParameter.FUEL_LEVEL: DESCRIPTIONS[CompitParameter.FUEL_LEVEL],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    44: CompitDeviceDescription(
        name="SolarComp 951",
        parameters={
            CompitParameter.COLLECTOR_POWER: DESCRIPTIONS[
                CompitParameter.COLLECTOR_POWER
            ],
            CompitParameter.COLLECTOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.COLLECTOR_TEMPERATURE
            ],
            CompitParameter.TANK_BOTTOM_T2_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.TANK_BOTTOM_T2_TEMPERATURE
            ],
            CompitParameter.TANK_T4_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.TANK_T4_TEMPERATURE
            ],
            CompitParameter.TANK_TOP_T3_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.TANK_TOP_T3_TEMPERATURE
            ],
        },
    ),
    45: CompitDeviceDescription(
        name="SolarComp971",
        parameters={
            CompitParameter.COLLECTOR_POWER: DESCRIPTIONS[
                CompitParameter.COLLECTOR_POWER
            ],
            CompitParameter.COLLECTOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.COLLECTOR_TEMPERATURE
            ],
            CompitParameter.ENERGY_TODAY: DESCRIPTIONS[CompitParameter.ENERGY_TODAY],
            CompitParameter.TANK_BOTTOM_T2_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.TANK_BOTTOM_T2_TEMPERATURE
            ],
            CompitParameter.TANK_TOP_T3_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.TANK_TOP_T3_TEMPERATURE
            ],
        },
    ),
    53: CompitDeviceDescription(
        name="R350.CWU",
        parameters={
            CompitParameter.CALCULATED_TARGET_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.CALCULATED_TARGET_TEMPERATURE
            ],
            CompitParameter.DHW_MEASURED_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.DHW_MEASURED_TEMPERATURE
            ],
            CompitParameter.ENERGY_SGREADY_YESTERDAY: DESCRIPTIONS[
                CompitParameter.ENERGY_SGREADY_YESTERDAY
            ],
            CompitParameter.ENERGY_TOTAL: DESCRIPTIONS[CompitParameter.ENERGY_TOTAL],
            CompitParameter.ENERGY_YESTERDAY: DESCRIPTIONS[
                CompitParameter.ENERGY_YESTERDAY
            ],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    58: CompitDeviceDescription(
        name="SolarComp 971SD1",
        parameters={
            CompitParameter.ENERGY_CONSUMPTION: DESCRIPTIONS[
                CompitParameter.ENERGY_CONSUMPTION
            ],
        },
    ),
    75: CompitDeviceDescription(
        name="BioMax772",
        parameters={
            CompitParameter.BOILER_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.BOILER_TEMPERATURE
            ],
            CompitParameter.FUEL_LEVEL: DESCRIPTIONS[CompitParameter.FUEL_LEVEL],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    78: CompitDeviceDescription(
        name="SPM - Nano Color 2",
        parameters={
            CompitParameter.CO2_LEVEL: DESCRIPTIONS[CompitParameter.CO2_LEVEL],
            CompitParameter.CO2_PERCENT: DESCRIPTIONS[CompitParameter.CO2_PERCENT],
            CompitParameter.HUMIDITY: DESCRIPTIONS[CompitParameter.HUMIDITY],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
            CompitParameter.PM1_LEVEL_MEASURED: DESCRIPTIONS[
                CompitParameter.PM1_LEVEL_MEASURED
            ],
            CompitParameter.PM4_LEVEL_MEASURED: DESCRIPTIONS[
                CompitParameter.PM4_LEVEL_MEASURED
            ],
            CompitParameter.PM10_MEASURED: DESCRIPTIONS[CompitParameter.PM10_MEASURED],
            CompitParameter.PM25_MEASURED: DESCRIPTIONS[CompitParameter.PM25_MEASURED],
        },
    ),
    91: CompitDeviceDescription(
        name="R770RS / R771RS ",
        parameters={
            CompitParameter.BOILER_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.BOILER_TEMPERATURE
            ],
            CompitParameter.FUEL_LEVEL: DESCRIPTIONS[CompitParameter.FUEL_LEVEL],
            CompitParameter.MIXER1_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.MIXER1_TEMPERATURE
            ],
            CompitParameter.MIXER2_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.MIXER2_TEMPERATURE
            ],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    92: CompitDeviceDescription(
        name="r490",
        parameters={
            CompitParameter.LOWER_SOURCE_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.LOWER_SOURCE_TEMPERATURE
            ],
            CompitParameter.UPPER_SOURCE_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.UPPER_SOURCE_TEMPERATURE
            ],
        },
    ),
    99: CompitDeviceDescription(
        name="SolarComp971C",
        parameters={
            CompitParameter.COLLECTOR_POWER: DESCRIPTIONS[
                CompitParameter.COLLECTOR_POWER
            ],
            CompitParameter.COLLECTOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.COLLECTOR_TEMPERATURE
            ],
            CompitParameter.ENERGY_TODAY: DESCRIPTIONS[CompitParameter.ENERGY_TODAY],
            CompitParameter.TANK_BOTTOM_T2_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.TANK_BOTTOM_T2_TEMPERATURE
            ],
            CompitParameter.TANK_TOP_T3_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.TANK_TOP_T3_TEMPERATURE
            ],
        },
    ),
    201: CompitDeviceDescription(
        name="BioMax775",
        parameters={
            CompitParameter.BOILER_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.BOILER_TEMPERATURE
            ],
            CompitParameter.FUEL_LEVEL: DESCRIPTIONS[CompitParameter.FUEL_LEVEL],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    210: CompitDeviceDescription(
        name="EL750",
        parameters={
            CompitParameter.BOILER_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.BOILER_TEMPERATURE
            ],
            CompitParameter.BUFFER_RETURN_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.BUFFER_RETURN_TEMPERATURE
            ],
            CompitParameter.DHW_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.DHW_TEMPERATURE
            ],
        },
    ),
    212: CompitDeviceDescription(
        name="BioMax742",
        parameters={
            CompitParameter.BOILER_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.BOILER_TEMPERATURE
            ],
            CompitParameter.FUEL_LEVEL: DESCRIPTIONS[CompitParameter.FUEL_LEVEL],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    215: CompitDeviceDescription(
        name="R480",
        parameters={
            CompitParameter.ACTUAL_BUFFER_TEMP: DESCRIPTIONS[
                CompitParameter.ACTUAL_BUFFER_TEMP
            ],
            CompitParameter.ACTUAL_DHW_TEMP: DESCRIPTIONS[
                CompitParameter.ACTUAL_DHW_TEMP
            ],
            CompitParameter.DHW_MEASURED_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.DHW_MEASURED_TEMPERATURE
            ],
        },
    ),
    221: CompitDeviceDescription(
        name="R350.M",
        parameters={
            CompitParameter.MIXER_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.MIXER_TEMPERATURE
            ],
            CompitParameter.PROTECTION_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.PROTECTION_TEMPERATURE
            ],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    222: CompitDeviceDescription(
        name="R377B",
        parameters={
            CompitParameter.BUFFER_SET_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.BUFFER_SET_TEMPERATURE
            ],
        },
    ),
    223: CompitDeviceDescription(
        name="Nano Color 2",
        parameters={
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
            CompitParameter.PM10_LEVEL: DESCRIPTIONS[CompitParameter.PM10_LEVEL],
            CompitParameter.PM25_LEVEL: DESCRIPTIONS[CompitParameter.PM25_LEVEL],
            CompitParameter.VENTILATION_ALARM: DESCRIPTIONS[
                CompitParameter.VENTILATION_ALARM
            ],
            CompitParameter.VENTILATION_GEAR: DESCRIPTIONS[
                CompitParameter.VENTILATION_GEAR
            ],
        },
    ),
    224: CompitDeviceDescription(
        name="R 900",
        parameters={
            CompitParameter.ACTUAL_BUFFER_TEMP: DESCRIPTIONS[
                CompitParameter.ACTUAL_BUFFER_TEMP
            ],
            CompitParameter.ACTUAL_HC1_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.ACTUAL_HC1_TEMPERATURE
            ],
            CompitParameter.ACTUAL_HC2_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.ACTUAL_HC2_TEMPERATURE
            ],
            CompitParameter.ACTUAL_HC3_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.ACTUAL_HC3_TEMPERATURE
            ],
            CompitParameter.ACTUAL_HC4_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.ACTUAL_HC4_TEMPERATURE
            ],
            CompitParameter.ACTUAL_DHW_TEMP: DESCRIPTIONS[
                CompitParameter.ACTUAL_DHW_TEMP
            ],
            CompitParameter.ACTUAL_UPPER_SOURCE_TEMP: DESCRIPTIONS[
                CompitParameter.ACTUAL_UPPER_SOURCE_TEMP
            ],
            CompitParameter.CALCULATED_BUFFER_TEMP: DESCRIPTIONS[
                CompitParameter.CALCULATED_BUFFER_TEMP
            ],
            CompitParameter.CALCULATED_DHW_TEMP: DESCRIPTIONS[
                CompitParameter.CALCULATED_DHW_TEMP
            ],
            CompitParameter.CALCULATED_UPPER_SOURCE_TEMP: DESCRIPTIONS[
                CompitParameter.CALCULATED_UPPER_SOURCE_TEMP
            ],
            CompitParameter.HEATING1_TARGET_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.HEATING1_TARGET_TEMPERATURE
            ],
            CompitParameter.HEATING2_TARGET_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.HEATING2_TARGET_TEMPERATURE
            ],
            CompitParameter.HEATING3_TARGET_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.HEATING3_TARGET_TEMPERATURE
            ],
            CompitParameter.HEATING4_TARGET_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.HEATING4_TARGET_TEMPERATURE
            ],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
        },
    ),
    225: CompitDeviceDescription(
        name="SPM - Nano Color",
        parameters={
            CompitParameter.HUMIDITY: DESCRIPTIONS[CompitParameter.HUMIDITY],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
            CompitParameter.PM10_MEASURED: DESCRIPTIONS[CompitParameter.PM10_MEASURED],
            CompitParameter.PM25_MEASURED: DESCRIPTIONS[CompitParameter.PM25_MEASURED],
        },
    ),
    226: CompitDeviceDescription(
        name="AF-1",
        parameters={
            CompitParameter.ALARM_CODE: DESCRIPTIONS[CompitParameter.ALARM_CODE],
            CompitParameter.BATTERY_LEVEL: DESCRIPTIONS[CompitParameter.BATTERY_LEVEL],
            CompitParameter.CHARGING_POWER: DESCRIPTIONS[
                CompitParameter.CHARGING_POWER
            ],
            CompitParameter.OUTDOOR_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.OUTDOOR_TEMPERATURE
            ],
            CompitParameter.RETURN_CIRCUIT_TEMPERATURE: DESCRIPTIONS[
                CompitParameter.RETURN_CIRCUIT_TEMPERATURE
            ],
        },
    ),
    227: CompitDeviceDescription(
        name="Combo",
        parameters={
            CompitParameter.PK1_FUNCTION: DESCRIPTIONS[CompitParameter.PK1_FUNCTION],
        },
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Compit sensor entities from a config entry."""

    coordinator = entry.runtime_data
    sensor_entities = []
    for device_id, device in coordinator.connector.all_devices.items():
        device_definition = DEVICE_DEFINITIONS.get(device.definition.code)

        if not device_definition:
            continue

        for code, entity_description in device_definition.parameters.items():
            if (
                entity_description.options
                and NO_SENSOR in entity_description.options
                and (
                    coordinator.connector.get_current_value(device_id, code)
                    == NO_SENSOR
                )
            ):
                continue

            sensor_entities.append(
                CompitSensor(
                    coordinator,
                    device_id,
                    device_definition.name,
                    code,
                    entity_description,
                )
            )

    async_add_devices(sensor_entities)


class CompitSensor(CoordinatorEntity[CompitDataUpdateCoordinator], SensorEntity):
    """Representation of a Compit sensor entity."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device_id: int,
        device_name: str,
        parameter_code: CompitParameter,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = entity_description
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device_name,
            manufacturer=MANUFACTURER_NAME,
            model=device_name,
        )
        self.parameter_code = parameter_code

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.connector.get_device(self.device_id) is not None
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        value = self.coordinator.connector.get_current_value(
            self.device_id, self.parameter_code
        )

        if (
            isinstance(value, str)
            and self.entity_description.options
            and value in self.entity_description.options
        ):
            return value

        if isinstance(value, (int, float)):
            return value

        return None
