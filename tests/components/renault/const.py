"""Constants for the Renault integration tests."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.renault.const import (
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_LOCALE,
    DEVICE_CLASS_CHARGE_MODE,
    DEVICE_CLASS_CHARGE_STATE,
    DEVICE_CLASS_PLUG_STATE,
    DOMAIN,
)
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.select.const import ATTR_OPTIONS
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_SW_VERSION,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    ELECTRIC_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    POWER_KILO_WATT,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TIME_MINUTES,
    VOLUME_LITERS,
)

ATTR_DEFAULT_DISABLED = "default_disabled"
ATTR_UNIQUE_ID = "unique_id"

FIXED_ATTRIBUTES = (
    ATTR_DEVICE_CLASS,
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
)
DYNAMIC_ATTRIBUTES = (ATTR_ICON,)

ICON_FOR_EMPTY_VALUES = {
    "select.reg_number_charge_mode": "mdi:calendar-remove",
    "sensor.reg_number_charge_state": "mdi:flash-off",
    "sensor.reg_number_plug_state": "mdi:power-plug-off",
}

MOCK_ACCOUNT_ID = "account_id_1"

# Mock config data to be used across multiple tests
MOCK_CONFIG = {
    CONF_USERNAME: "email@test.com",
    CONF_PASSWORD: "test",
    CONF_KAMEREON_ACCOUNT_ID: "account_id_1",
    CONF_LOCALE: "fr_FR",
}

MOCK_VEHICLES = {
    "zoe_40": {
        "expected_device": {
            ATTR_IDENTIFIERS: {(DOMAIN, "VF1AAAAA555777999")},
            ATTR_MANUFACTURER: "Renault",
            ATTR_MODEL: "Zoe",
            ATTR_NAME: "REG-NUMBER",
            ATTR_SW_VERSION: "X101VE",
        },
        "endpoints_available": [
            True,  # cockpit
            True,  # hvac-status
            False,  # location
            True,  # battery-status
            True,  # charge-mode
        ],
        "endpoints": {
            "battery_status": "battery_status_charging.json",
            "charge_mode": "charge_mode_always.json",
            "cockpit": "cockpit_ev.json",
            "hvac_status": "hvac_status.json",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG,
                ATTR_ENTITY_ID: "binary_sensor.reg_number_plugged_in",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_plugged_in",
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY_CHARGING,
                ATTR_ENTITY_ID: "binary_sensor.reg_number_charging",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charging",
            },
        ],
        BUTTON_DOMAIN: [
            {
                ATTR_ENTITY_ID: "button.reg_number_start_air_conditioner",
                ATTR_ICON: "mdi:air-conditioner",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_start_air_conditioner",
            },
            {
                ATTR_ENTITY_ID: "button.reg_number_start_charge",
                ATTR_ICON: "mdi:ev-station",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_start_charge",
            },
        ],
        DEVICE_TRACKER_DOMAIN: [],
        SELECT_DOMAIN: [
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_MODE,
                ATTR_ENTITY_ID: "select.reg_number_charge_mode",
                ATTR_ICON: "mdi:calendar-remove",
                ATTR_OPTIONS: ["always", "always_charging", "schedule_mode"],
                ATTR_STATE: "always",
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charge_mode",
            },
        ],
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.reg_number_battery_autonomy",
                ATTR_ICON: "mdi:ev-station",
                ATTR_STATE: "141",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_autonomy",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_available_energy",
                ATTR_STATE: "31",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_available_energy",
                ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_level",
                ATTR_STATE: "60",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_level",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_last_activity",
                ATTR_STATE: "2020-01-12T21:40:16+00:00",
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_last_activity",
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_temperature",
                ATTR_STATE: "20",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_temperature",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_STATE,
                ATTR_ENTITY_ID: "sensor.reg_number_charge_state",
                ATTR_ICON: "mdi:flash",
                ATTR_STATE: "charge_in_progress",
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charge_state",
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
                ATTR_ENTITY_ID: "sensor.reg_number_charging_power",
                ATTR_STATE: "0.027",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charging_power",
                ATTR_UNIT_OF_MEASUREMENT: POWER_KILO_WATT,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_charging_remaining_time",
                ATTR_ICON: "mdi:timer",
                ATTR_STATE: "145",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charging_remaining_time",
                ATTR_UNIT_OF_MEASUREMENT: TIME_MINUTES,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_mileage",
                ATTR_ICON: "mdi:sign-direction",
                ATTR_STATE: "49114",
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_mileage",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.reg_number_outside_temperature",
                ATTR_STATE: "8.0",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_outside_temperature",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG_STATE,
                ATTR_ENTITY_ID: "sensor.reg_number_plug_state",
                ATTR_ICON: "mdi:power-plug",
                ATTR_STATE: "plugged",
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_plug_state",
            },
        ],
    },
    "zoe_50": {
        "expected_device": {
            ATTR_IDENTIFIERS: {(DOMAIN, "VF1AAAAA555777999")},
            ATTR_MANUFACTURER: "Renault",
            ATTR_MODEL: "Zoe",
            ATTR_NAME: "REG-NUMBER",
            ATTR_SW_VERSION: "X102VE",
        },
        "endpoints_available": [
            True,  # cockpit
            False,  # hvac-status
            True,  # location
            True,  # battery-status
            True,  # charge-mode
        ],
        "endpoints": {
            "battery_status": "battery_status_not_charging.json",
            "charge_mode": "charge_mode_schedule.json",
            "cockpit": "cockpit_ev.json",
            "location": "location.json",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG,
                ATTR_ENTITY_ID: "binary_sensor.reg_number_plugged_in",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_plugged_in",
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY_CHARGING,
                ATTR_ENTITY_ID: "binary_sensor.reg_number_charging",
                ATTR_STATE: STATE_OFF,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charging",
            },
        ],
        BUTTON_DOMAIN: [
            {
                ATTR_ENTITY_ID: "button.reg_number_start_air_conditioner",
                ATTR_ICON: "mdi:air-conditioner",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_start_air_conditioner",
            },
            {
                ATTR_ENTITY_ID: "button.reg_number_start_charge",
                ATTR_ICON: "mdi:ev-station",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_start_charge",
            },
        ],
        DEVICE_TRACKER_DOMAIN: [
            {
                ATTR_ENTITY_ID: "device_tracker.reg_number_location",
                ATTR_ICON: "mdi:car",
                ATTR_STATE: STATE_NOT_HOME,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_location",
            }
        ],
        SELECT_DOMAIN: [
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_MODE,
                ATTR_ENTITY_ID: "select.reg_number_charge_mode",
                ATTR_ICON: "mdi:calendar-clock",
                ATTR_OPTIONS: ["always", "always_charging", "schedule_mode"],
                ATTR_STATE: "schedule_mode",
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charge_mode",
            },
        ],
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.reg_number_battery_autonomy",
                ATTR_ICON: "mdi:ev-station",
                ATTR_STATE: "128",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_autonomy",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_available_energy",
                ATTR_STATE: "0",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_available_energy",
                ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_level",
                ATTR_STATE: "50",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_level",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_last_activity",
                ATTR_STATE: "2020-11-17T08:06:48+00:00",
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_last_activity",
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_temperature",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_battery_temperature",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_STATE,
                ATTR_ENTITY_ID: "sensor.reg_number_charge_state",
                ATTR_ICON: "mdi:flash-off",
                ATTR_STATE: "charge_error",
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charge_state",
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
                ATTR_ENTITY_ID: "sensor.reg_number_charging_power",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charging_power",
                ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_charging_remaining_time",
                ATTR_ICON: "mdi:timer",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_charging_remaining_time",
                ATTR_UNIT_OF_MEASUREMENT: TIME_MINUTES,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_mileage",
                ATTR_ICON: "mdi:sign-direction",
                ATTR_STATE: "49114",
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_mileage",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG_STATE,
                ATTR_ENTITY_ID: "sensor.reg_number_plug_state",
                ATTR_ICON: "mdi:power-plug-off",
                ATTR_STATE: "unplugged",
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_plug_state",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
                ATTR_ENTITY_ID: "sensor.reg_number_location_last_activity",
                ATTR_STATE: "2020-02-18T16:58:38+00:00",
                ATTR_UNIQUE_ID: "vf1aaaaa555777999_location_last_activity",
            },
        ],
    },
    "captur_phev": {
        "expected_device": {
            ATTR_IDENTIFIERS: {(DOMAIN, "VF1AAAAA555777123")},
            ATTR_MANUFACTURER: "Renault",
            ATTR_MODEL: "Captur ii",
            ATTR_NAME: "REG-NUMBER",
            ATTR_SW_VERSION: "XJB1SU",
        },
        "endpoints_available": [
            True,  # cockpit
            False,  # hvac-status
            True,  # location
            True,  # battery-status
            True,  # charge-mode
        ],
        "endpoints": {
            "battery_status": "battery_status_charging.json",
            "charge_mode": "charge_mode_always.json",
            "cockpit": "cockpit_fuel.json",
            "location": "location.json",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG,
                ATTR_ENTITY_ID: "binary_sensor.reg_number_plugged_in",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_plugged_in",
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY_CHARGING,
                ATTR_ENTITY_ID: "binary_sensor.reg_number_charging",
                ATTR_STATE: STATE_ON,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_charging",
            },
        ],
        BUTTON_DOMAIN: [
            {
                ATTR_ENTITY_ID: "button.reg_number_start_air_conditioner",
                ATTR_ICON: "mdi:air-conditioner",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_start_air_conditioner",
            },
            {
                ATTR_ENTITY_ID: "button.reg_number_start_charge",
                ATTR_ICON: "mdi:ev-station",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_start_charge",
            },
        ],
        DEVICE_TRACKER_DOMAIN: [
            {
                ATTR_ENTITY_ID: "device_tracker.reg_number_location",
                ATTR_ICON: "mdi:car",
                ATTR_STATE: STATE_NOT_HOME,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_location",
            }
        ],
        SELECT_DOMAIN: [
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_MODE,
                ATTR_ENTITY_ID: "select.reg_number_charge_mode",
                ATTR_ICON: "mdi:calendar-remove",
                ATTR_OPTIONS: ["always", "always_charging", "schedule_mode"],
                ATTR_STATE: "always",
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_charge_mode",
            },
        ],
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.reg_number_battery_autonomy",
                ATTR_ICON: "mdi:ev-station",
                ATTR_STATE: "141",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_battery_autonomy",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_available_energy",
                ATTR_STATE: "31",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_battery_available_energy",
                ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_level",
                ATTR_STATE: "60",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_battery_level",
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_last_activity",
                ATTR_STATE: "2020-01-12T21:40:16+00:00",
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_battery_last_activity",
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_ENTITY_ID: "sensor.reg_number_battery_temperature",
                ATTR_STATE: "20",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_battery_temperature",
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_STATE,
                ATTR_ENTITY_ID: "sensor.reg_number_charge_state",
                ATTR_ICON: "mdi:flash",
                ATTR_STATE: "charge_in_progress",
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_charge_state",
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
                ATTR_ENTITY_ID: "sensor.reg_number_charging_power",
                ATTR_STATE: "27.0",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_charging_power",
                ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_charging_remaining_time",
                ATTR_ICON: "mdi:timer",
                ATTR_STATE: "145",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_charging_remaining_time",
                ATTR_UNIT_OF_MEASUREMENT: TIME_MINUTES,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_fuel_autonomy",
                ATTR_ICON: "mdi:gas-station",
                ATTR_STATE: "35",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_fuel_autonomy",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_fuel_quantity",
                ATTR_ICON: "mdi:fuel",
                ATTR_STATE: "3",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_fuel_quantity",
                ATTR_UNIT_OF_MEASUREMENT: VOLUME_LITERS,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_mileage",
                ATTR_ICON: "mdi:sign-direction",
                ATTR_STATE: "5567",
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_mileage",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG_STATE,
                ATTR_ENTITY_ID: "sensor.reg_number_plug_state",
                ATTR_ICON: "mdi:power-plug",
                ATTR_STATE: "plugged",
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_plug_state",
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
                ATTR_ENTITY_ID: "sensor.reg_number_location_last_activity",
                ATTR_STATE: "2020-02-18T16:58:38+00:00",
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_location_last_activity",
            },
        ],
    },
    "captur_fuel": {
        "expected_device": {
            ATTR_IDENTIFIERS: {(DOMAIN, "VF1AAAAA555777123")},
            ATTR_MANUFACTURER: "Renault",
            ATTR_MODEL: "Captur ii",
            ATTR_NAME: "REG-NUMBER",
            ATTR_SW_VERSION: "XJB1SU",
        },
        "endpoints_available": [
            True,  # cockpit
            False,  # hvac-status
            True,  # location
            # Ignore,  # battery-status
            # Ignore,  # charge-mode
        ],
        "endpoints": {
            "cockpit": "cockpit_fuel.json",
            "location": "location.json",
        },
        BINARY_SENSOR_DOMAIN: [],
        BUTTON_DOMAIN: [
            {
                ATTR_ENTITY_ID: "button.reg_number_start_air_conditioner",
                ATTR_ICON: "mdi:air-conditioner",
                ATTR_STATE: STATE_UNKNOWN,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_start_air_conditioner",
            },
        ],
        DEVICE_TRACKER_DOMAIN: [
            {
                ATTR_ENTITY_ID: "device_tracker.reg_number_location",
                ATTR_ICON: "mdi:car",
                ATTR_STATE: STATE_NOT_HOME,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_location",
            }
        ],
        SELECT_DOMAIN: [],
        SENSOR_DOMAIN: [
            {
                ATTR_ENTITY_ID: "sensor.reg_number_fuel_autonomy",
                ATTR_ICON: "mdi:gas-station",
                ATTR_STATE: "35",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_fuel_autonomy",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_fuel_quantity",
                ATTR_ICON: "mdi:fuel",
                ATTR_STATE: "3",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_fuel_quantity",
                ATTR_UNIT_OF_MEASUREMENT: VOLUME_LITERS,
            },
            {
                ATTR_ENTITY_ID: "sensor.reg_number_mileage",
                ATTR_ICON: "mdi:sign-direction",
                ATTR_STATE: "5567",
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_mileage",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                ATTR_DEFAULT_DISABLED: True,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
                ATTR_ENTITY_ID: "sensor.reg_number_location_last_activity",
                ATTR_STATE: "2020-02-18T16:58:38+00:00",
                ATTR_UNIQUE_ID: "vf1aaaaa555777123_location_last_activity",
            },
        ],
    },
}
