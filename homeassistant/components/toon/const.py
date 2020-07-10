"""Constants for the Toon integration."""
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
)
from homeassistant.components.sensor import DEVICE_CLASS_POWER, DEVICE_CLASS_TEMPERATURE
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)

DOMAIN = "toon"

CONF_AGREEMENT = "agreement"
CONF_AGREEMENT_ID = "agreement_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_MIGRATE = "migrate"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=300)
DEFAULT_MAX_TEMP = 30.0
DEFAULT_MIN_TEMP = 6.0

CURRENCY_EUR = "EUR"
VOLUME_CM3 = "CM3"
VOLUME_M3 = "M3"

ATTR_DEFAULT_ENABLED = "default_enabled"
ATTR_INVERTED = "inverted"
ATTR_MEASUREMENT = "measurement"
ATTR_SECTION = "section"

BINARY_SENSOR_ENTITIES = {
    "thermostat_info_boiler_connected_None": {
        ATTR_NAME: "Boiler Module Connection",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "boiler_module_connected",
        ATTR_INVERTED: False,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_CONNECTIVITY,
        ATTR_ICON: "mdi:check-network-outline",
        ATTR_DEFAULT_ENABLED: False,
    },
    "thermostat_info_burner_info_1": {
        ATTR_NAME: "Boiler Heating",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "heating",
        ATTR_INVERTED: False,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:fire",
        ATTR_DEFAULT_ENABLED: False,
    },
    "thermostat_info_burner_info_2": {
        ATTR_NAME: "Hot Tap Water",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "hot_tapwater",
        ATTR_INVERTED: False,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:water-pump",
        ATTR_DEFAULT_ENABLED: True,
    },
    "thermostat_info_burner_info_3": {
        ATTR_NAME: "Boiler Preheating",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "pre_heating",
        ATTR_INVERTED: False,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:fire",
        ATTR_DEFAULT_ENABLED: False,
    },
    "thermostat_info_burner_info_None": {
        ATTR_NAME: "Boiler Burner",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "burner",
        ATTR_INVERTED: False,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:fire",
        ATTR_DEFAULT_ENABLED: True,
    },
    "thermostat_info_error_found_255": {
        ATTR_NAME: "Boiler Status",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "error_found",
        ATTR_INVERTED: False,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
        ATTR_ICON: "mdi:alert",
        ATTR_DEFAULT_ENABLED: True,
    },
    "thermostat_info_ot_communication_error_0": {
        ATTR_NAME: "OpenTherm Connection",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "opentherm_communication_error",
        ATTR_INVERTED: False,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
        ATTR_ICON: "mdi:check-network-outline",
        ATTR_DEFAULT_ENABLED: False,
    },
    "thermostat_program_overridden": {
        ATTR_NAME: "Thermostat Program Override",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "program_overridden",
        ATTR_INVERTED: False,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:gesture-tap",
        ATTR_DEFAULT_ENABLED: True,
    },
}

SENSOR_ENTITIES = {
    "current_display_temperature": {
        ATTR_NAME: "Temperature",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "current_display_temperature",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_DEFAULT_ENABLED: False,
    },
    "gas_average": {
        ATTR_NAME: "Average Gas Usage",
        ATTR_SECTION: "gas_usage",
        ATTR_MEASUREMENT: "average",
        ATTR_UNIT_OF_MEASUREMENT: VOLUME_CM3,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:gas-cylinder",
        ATTR_DEFAULT_ENABLED: True,
    },
    "gas_average_daily": {
        ATTR_NAME: "Average Daily Gas Usage",
        ATTR_SECTION: "gas_usage",
        ATTR_MEASUREMENT: "day_average",
        ATTR_UNIT_OF_MEASUREMENT: VOLUME_M3,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:gas-cylinder",
        ATTR_DEFAULT_ENABLED: False,
    },
    "gas_daily_usage": {
        ATTR_NAME: "Gas Usage Today",
        ATTR_SECTION: "gas_usage",
        ATTR_MEASUREMENT: "day_usage",
        ATTR_UNIT_OF_MEASUREMENT: VOLUME_M3,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:gas-cylinder",
        ATTR_DEFAULT_ENABLED: True,
    },
    "gas_daily_cost": {
        ATTR_NAME: "Gas Cost Today",
        ATTR_SECTION: "gas_usage",
        ATTR_MEASUREMENT: "day_cost",
        ATTR_UNIT_OF_MEASUREMENT: CURRENCY_EUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:gas-cylinder",
        ATTR_DEFAULT_ENABLED: True,
    },
    "gas_meter_reading": {
        ATTR_NAME: "Gas Meter",
        ATTR_SECTION: "gas_usage",
        ATTR_MEASUREMENT: "meter",
        ATTR_UNIT_OF_MEASUREMENT: VOLUME_M3,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:gas-cylinder",
        ATTR_DEFAULT_ENABLED: False,
    },
    "gas_value": {
        ATTR_NAME: "Current Gas Usage",
        ATTR_SECTION: "gas_usage",
        ATTR_MEASUREMENT: "current",
        ATTR_UNIT_OF_MEASUREMENT: VOLUME_CM3,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:gas-cylinder",
        ATTR_DEFAULT_ENABLED: True,
    },
    "power_average": {
        ATTR_NAME: "Average Power Usage",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "average",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: False,
    },
    "power_average_daily": {
        ATTR_NAME: "Average Daily Energy Usage",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "day_average",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: False,
    },
    "power_daily_cost": {
        ATTR_NAME: "Energy Cost Today",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "day_cost",
        ATTR_UNIT_OF_MEASUREMENT: CURRENCY_EUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: True,
    },
    "power_daily_value": {
        ATTR_NAME: "Energy Usage Today",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "day_usage",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: True,
    },
    "power_meter_reading": {
        ATTR_NAME: "Electricity Meter Feed IN Tariff 1",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "meter_high",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: False,
    },
    "power_meter_reading_low": {
        ATTR_NAME: "Electricity Meter Feed IN Tariff 2",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "meter_high",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: False,
    },
    "power_value": {
        ATTR_NAME: "Current Power Usage",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "current",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: True,
    },
    "solar_meter_reading_produced": {
        ATTR_NAME: "Electricity Meter Feed OUT Tariff 1",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "meter_produced_high",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: False,
    },
    "solar_meter_reading_low_produced": {
        ATTR_NAME: "Electricity Meter Feed OUT Tariff 2",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "meter_produced_low",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: False,
    },
    "solar_value": {
        ATTR_NAME: "Current Solar Power Production",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "current_solar",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_ICON: "mdi:solar-power",
        ATTR_DEFAULT_ENABLED: True,
    },
    "solar_maximum": {
        ATTR_NAME: "Max Solar Power Production Today",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "day_max_solar",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:solar-power",
        ATTR_DEFAULT_ENABLED: True,
    },
    "solar_produced": {
        ATTR_NAME: "Solar Power Production to Grid",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "current_produced",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_ICON: "mdi:solar-power",
        ATTR_DEFAULT_ENABLED: True,
    },
    "power_usage_day_produced_solar": {
        ATTR_NAME: "Solar Energy Produced Today",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "day_produced_solar",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:solar-power",
        ATTR_DEFAULT_ENABLED: True,
    },
    "power_usage_day_to_grid_usage": {
        ATTR_NAME: "Energy Produced To Grid Today",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "day_to_grid_usage",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:solar-power",
        ATTR_DEFAULT_ENABLED: False,
    },
    "power_usage_day_from_grid_usage": {
        ATTR_NAME: "Energy Usage From Grid Today",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "day_from_grid_usage",
        ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:power-plug",
        ATTR_DEFAULT_ENABLED: False,
    },
    "solar_average_produced": {
        ATTR_NAME: "Average Solar Power Production to Grid",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "average_produced",
        ATTR_UNIT_OF_MEASUREMENT: POWER_WATT,
        ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
        ATTR_ICON: "mdi:solar-power",
        ATTR_DEFAULT_ENABLED: False,
    },
    "thermostat_info_current_modulation_level": {
        ATTR_NAME: "Boiler Modulation Level",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "current_modulation_level",
        ATTR_UNIT_OF_MEASUREMENT: UNIT_PERCENTAGE,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:percent",
        ATTR_DEFAULT_ENABLED: False,
    },
    "power_usage_current_covered_by_solar": {
        ATTR_NAME: "Current Power Usage Covered By Solar",
        ATTR_SECTION: "power_usage",
        ATTR_MEASUREMENT: "current_covered_by_solar",
        ATTR_UNIT_OF_MEASUREMENT: UNIT_PERCENTAGE,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:solar-power",
        ATTR_DEFAULT_ENABLED: True,
    },
}

SWITCH_ENTITIES = {
    "thermostat_holiday_mode": {
        ATTR_NAME: "Holiday Mode",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "holiday_mode",
        ATTR_INVERTED: False,
        ATTR_ICON: "mdi:airport",
        ATTR_DEFAULT_ENABLED: True,
    },
    "thermostat_program": {
        ATTR_NAME: "Thermostat Program",
        ATTR_SECTION: "thermostat",
        ATTR_MEASUREMENT: "program",
        ATTR_INVERTED: False,
        ATTR_ICON: "mdi:calendar-clock",
        ATTR_DEFAULT_ENABLED: True,
    },
}
