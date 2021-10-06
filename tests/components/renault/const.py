"""Constants for the Renault integration tests."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.renault.const import (
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_LOCALE,
    DEVICE_CLASS_CHARGE_MODE,
    DEVICE_CLASS_CHARGE_STATE,
    DEVICE_CLASS_PLUG_STATE,
    DOMAIN,
)
from homeassistant.components.renault.renault_entities import ATTR_LAST_UPDATE
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
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
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

FIXED_ATTRIBUTES = (
    ATTR_DEVICE_CLASS,
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
)
DYNAMIC_ATTRIBUTES = (
    ATTR_ICON,
    ATTR_LAST_UPDATE,
)

ICON_FOR_EMPTY_VALUES = {
    "select.charge_mode": "mdi:calendar-remove",
    "sensor.charge_state": "mdi:flash-off",
    "sensor.plug_state": "mdi:power-plug-off",
}

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
            "identifiers": {(DOMAIN, "VF1AAAAA555777999")},
            "manufacturer": "Renault",
            "model": "Zoe",
            "name": "REG-NUMBER",
            "sw_version": "X101VE",
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
                "entity_id": "binary_sensor.plugged_in",
                "unique_id": "vf1aaaaa555777999_plugged_in",
                "result": STATE_ON,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
            },
            {
                "entity_id": "binary_sensor.charging",
                "unique_id": "vf1aaaaa555777999_charging",
                "result": STATE_ON,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY_CHARGING,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
            },
        ],
        DEVICE_TRACKER_DOMAIN: [],
        SELECT_DOMAIN: [
            {
                "entity_id": "select.charge_mode",
                "unique_id": "vf1aaaaa555777999_charge_mode",
                "result": "always",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_MODE,
                ATTR_ICON: "mdi:calendar-remove",
                ATTR_OPTIONS: ["always", "always_charging", "schedule_mode"],
            },
        ],
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.battery_autonomy",
                "unique_id": "vf1aaaaa555777999_battery_autonomy",
                "result": "141",
                ATTR_ICON: "mdi:ev-station",
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.battery_available_energy",
                "unique_id": "vf1aaaaa555777999_battery_available_energy",
                "result": "31",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            },
            {
                "entity_id": "sensor.battery_level",
                "unique_id": "vf1aaaaa555777999_battery_level",
                "result": "60",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                "entity_id": "sensor.battery_temperature",
                "unique_id": "vf1aaaaa555777999_battery_temperature",
                "result": "20",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            },
            {
                "entity_id": "sensor.charge_state",
                "unique_id": "vf1aaaaa555777999_charge_state",
                "result": "charge_in_progress",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_STATE,
                ATTR_ICON: "mdi:flash",
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
            },
            {
                "entity_id": "sensor.charging_power",
                "unique_id": "vf1aaaaa555777999_charging_power",
                "result": "0.027",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_POWER,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: POWER_KILO_WATT,
            },
            {
                "entity_id": "sensor.charging_remaining_time",
                "unique_id": "vf1aaaaa555777999_charging_remaining_time",
                "result": "145",
                ATTR_ICON: "mdi:timer",
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: TIME_MINUTES,
            },
            {
                "entity_id": "sensor.mileage",
                "unique_id": "vf1aaaaa555777999_mileage",
                "result": "49114",
                ATTR_ICON: "mdi:sign-direction",
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.outside_temperature",
                "unique_id": "vf1aaaaa555777999_outside_temperature",
                "result": "8.0",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            },
            {
                "entity_id": "sensor.plug_state",
                "unique_id": "vf1aaaaa555777999_plug_state",
                "result": "plugged",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG_STATE,
                ATTR_ICON: "mdi:power-plug",
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
            },
        ],
    },
    "zoe_50": {
        "expected_device": {
            "identifiers": {(DOMAIN, "VF1AAAAA555777999")},
            "manufacturer": "Renault",
            "model": "Zoe",
            "name": "REG-NUMBER",
            "sw_version": "X102VE",
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
                "entity_id": "binary_sensor.plugged_in",
                "unique_id": "vf1aaaaa555777999_plugged_in",
                "result": STATE_OFF,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG,
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
            },
            {
                "entity_id": "binary_sensor.charging",
                "unique_id": "vf1aaaaa555777999_charging",
                "result": STATE_OFF,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY_CHARGING,
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
            },
        ],
        DEVICE_TRACKER_DOMAIN: [
            {
                "entity_id": "device_tracker.location",
                "unique_id": "vf1aaaaa555777999_location",
                "result": STATE_NOT_HOME,
                ATTR_ICON: "mdi:car",
                ATTR_LAST_UPDATE: "2020-02-18T16:58:38+00:00",
            }
        ],
        SELECT_DOMAIN: [
            {
                "entity_id": "select.charge_mode",
                "unique_id": "vf1aaaaa555777999_charge_mode",
                "result": "schedule_mode",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_MODE,
                ATTR_ICON: "mdi:calendar-clock",
                ATTR_OPTIONS: ["always", "always_charging", "schedule_mode"],
            },
        ],
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.battery_autonomy",
                "unique_id": "vf1aaaaa555777999_battery_autonomy",
                "result": "128",
                ATTR_ICON: "mdi:ev-station",
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.battery_available_energy",
                "unique_id": "vf1aaaaa555777999_battery_available_energy",
                "result": "0",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            },
            {
                "entity_id": "sensor.battery_level",
                "unique_id": "vf1aaaaa555777999_battery_level",
                "result": "50",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                "entity_id": "sensor.battery_temperature",
                "unique_id": "vf1aaaaa555777999_battery_temperature",
                "result": STATE_UNKNOWN,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            },
            {
                "entity_id": "sensor.charge_state",
                "unique_id": "vf1aaaaa555777999_charge_state",
                "result": "charge_error",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_STATE,
                ATTR_ICON: "mdi:flash-off",
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
            },
            {
                "entity_id": "sensor.charging_power",
                "unique_id": "vf1aaaaa555777999_charging_power",
                "result": STATE_UNKNOWN,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            },
            {
                "entity_id": "sensor.charging_remaining_time",
                "unique_id": "vf1aaaaa555777999_charging_remaining_time",
                "result": STATE_UNKNOWN,
                ATTR_ICON: "mdi:timer",
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: TIME_MINUTES,
            },
            {
                "entity_id": "sensor.mileage",
                "unique_id": "vf1aaaaa555777999_mileage",
                "result": "49114",
                ATTR_ICON: "mdi:sign-direction",
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.plug_state",
                "unique_id": "vf1aaaaa555777999_plug_state",
                "result": "unplugged",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG_STATE,
                ATTR_ICON: "mdi:power-plug-off",
                ATTR_LAST_UPDATE: "2020-11-17T08:06:48+00:00",
            },
        ],
    },
    "captur_phev": {
        "expected_device": {
            "identifiers": {(DOMAIN, "VF1AAAAA555777123")},
            "manufacturer": "Renault",
            "model": "Captur ii",
            "name": "REG-NUMBER",
            "sw_version": "XJB1SU",
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
                "entity_id": "binary_sensor.plugged_in",
                "unique_id": "vf1aaaaa555777123_plugged_in",
                "result": STATE_ON,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
            },
            {
                "entity_id": "binary_sensor.charging",
                "unique_id": "vf1aaaaa555777123_charging",
                "result": STATE_ON,
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY_CHARGING,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
            },
        ],
        DEVICE_TRACKER_DOMAIN: [
            {
                "entity_id": "device_tracker.location",
                "unique_id": "vf1aaaaa555777123_location",
                "result": STATE_NOT_HOME,
                ATTR_ICON: "mdi:car",
                ATTR_LAST_UPDATE: "2020-02-18T16:58:38+00:00",
            }
        ],
        SELECT_DOMAIN: [
            {
                "entity_id": "select.charge_mode",
                "unique_id": "vf1aaaaa555777123_charge_mode",
                "result": "always",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_MODE,
                ATTR_ICON: "mdi:calendar-remove",
                ATTR_OPTIONS: ["always", "always_charging", "schedule_mode"],
            },
        ],
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.battery_autonomy",
                "unique_id": "vf1aaaaa555777123_battery_autonomy",
                "result": "141",
                ATTR_ICON: "mdi:ev-station",
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.battery_available_energy",
                "unique_id": "vf1aaaaa555777123_battery_available_energy",
                "result": "31",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_ENERGY,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR,
            },
            {
                "entity_id": "sensor.battery_level",
                "unique_id": "vf1aaaaa555777123_battery_level",
                "result": "60",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            },
            {
                "entity_id": "sensor.battery_temperature",
                "unique_id": "vf1aaaaa555777123_battery_temperature",
                "result": "20",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            },
            {
                "entity_id": "sensor.charge_state",
                "unique_id": "vf1aaaaa555777123_charge_state",
                "result": "charge_in_progress",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CHARGE_STATE,
                ATTR_ICON: "mdi:flash",
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
            },
            {
                "entity_id": "sensor.charging_power",
                "unique_id": "vf1aaaaa555777123_charging_power",
                "result": "27.0",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_CURRENT,
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: ELECTRIC_CURRENT_AMPERE,
            },
            {
                "entity_id": "sensor.charging_remaining_time",
                "unique_id": "vf1aaaaa555777123_charging_remaining_time",
                "result": "145",
                ATTR_ICON: "mdi:timer",
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: TIME_MINUTES,
            },
            {
                "entity_id": "sensor.fuel_autonomy",
                "unique_id": "vf1aaaaa555777123_fuel_autonomy",
                "result": "35",
                ATTR_ICON: "mdi:gas-station",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.fuel_quantity",
                "unique_id": "vf1aaaaa555777123_fuel_quantity",
                "result": "3",
                ATTR_ICON: "mdi:fuel",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: VOLUME_LITERS,
            },
            {
                "entity_id": "sensor.mileage",
                "unique_id": "vf1aaaaa555777123_mileage",
                "result": "5567",
                ATTR_ICON: "mdi:sign-direction",
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.plug_state",
                "unique_id": "vf1aaaaa555777123_plug_state",
                "result": "plugged",
                ATTR_DEVICE_CLASS: DEVICE_CLASS_PLUG_STATE,
                ATTR_ICON: "mdi:power-plug",
                ATTR_LAST_UPDATE: "2020-01-12T21:40:16+00:00",
            },
        ],
    },
    "captur_fuel": {
        "expected_device": {
            "identifiers": {(DOMAIN, "VF1AAAAA555777123")},
            "manufacturer": "Renault",
            "model": "Captur ii",
            "name": "REG-NUMBER",
            "sw_version": "XJB1SU",
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
        DEVICE_TRACKER_DOMAIN: [
            {
                "entity_id": "device_tracker.location",
                "unique_id": "vf1aaaaa555777123_location",
                "result": STATE_NOT_HOME,
                ATTR_ICON: "mdi:car",
                ATTR_LAST_UPDATE: "2020-02-18T16:58:38+00:00",
            }
        ],
        SELECT_DOMAIN: [],
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.fuel_autonomy",
                "unique_id": "vf1aaaaa555777123_fuel_autonomy",
                "result": "35",
                ATTR_ICON: "mdi:gas-station",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.fuel_quantity",
                "unique_id": "vf1aaaaa555777123_fuel_quantity",
                "result": "3",
                ATTR_ICON: "mdi:fuel",
                ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: VOLUME_LITERS,
            },
            {
                "entity_id": "sensor.mileage",
                "unique_id": "vf1aaaaa555777123_mileage",
                "result": "5567",
                ATTR_ICON: "mdi:sign-direction",
                ATTR_STATE_CLASS: STATE_CLASS_TOTAL_INCREASING,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            },
        ],
    },
}
