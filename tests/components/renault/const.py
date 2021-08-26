"""Constants for the Renault integration tests."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    DOMAIN as BINARY_SENSOR_DOMAIN,
)
from homeassistant.components.renault.const import (
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_LOCALE,
    DEVICE_CLASS_CHARGE_MODE,
    DEVICE_CLASS_CHARGE_STATE,
    DEVICE_CLASS_PLUG_STATE,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    POWER_KILO_WATT,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TIME_MINUTES,
    VOLUME_LITERS,
)

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
                "class": DEVICE_CLASS_PLUG,
            },
            {
                "entity_id": "binary_sensor.charging",
                "unique_id": "vf1aaaaa555777999_charging",
                "result": STATE_ON,
                "class": DEVICE_CLASS_BATTERY_CHARGING,
            },
        ],
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.battery_autonomy",
                "unique_id": "vf1aaaaa555777999_battery_autonomy",
                "result": "141",
                "unit": LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.battery_available_energy",
                "unique_id": "vf1aaaaa555777999_battery_available_energy",
                "result": "31",
                "unit": ENERGY_KILO_WATT_HOUR,
                "class": DEVICE_CLASS_ENERGY,
            },
            {
                "entity_id": "sensor.battery_level",
                "unique_id": "vf1aaaaa555777999_battery_level",
                "result": "60",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_BATTERY,
            },
            {
                "entity_id": "sensor.battery_temperature",
                "unique_id": "vf1aaaaa555777999_battery_temperature",
                "result": "20",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
            {
                "entity_id": "sensor.charge_mode",
                "unique_id": "vf1aaaaa555777999_charge_mode",
                "result": "always",
                "class": DEVICE_CLASS_CHARGE_MODE,
            },
            {
                "entity_id": "sensor.charge_state",
                "unique_id": "vf1aaaaa555777999_charge_state",
                "result": "charge_in_progress",
                "class": DEVICE_CLASS_CHARGE_STATE,
            },
            {
                "entity_id": "sensor.charging_power",
                "unique_id": "vf1aaaaa555777999_charging_power",
                "result": "0.027",
                "unit": POWER_KILO_WATT,
                "class": DEVICE_CLASS_POWER,
            },
            {
                "entity_id": "sensor.charging_remaining_time",
                "unique_id": "vf1aaaaa555777999_charging_remaining_time",
                "result": "145",
                "unit": TIME_MINUTES,
            },
            {
                "entity_id": "sensor.mileage",
                "unique_id": "vf1aaaaa555777999_mileage",
                "result": "49114",
                "unit": LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.outside_temperature",
                "unique_id": "vf1aaaaa555777999_outside_temperature",
                "result": "8.0",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
            {
                "entity_id": "sensor.plug_state",
                "unique_id": "vf1aaaaa555777999_plug_state",
                "result": "plugged",
                "class": DEVICE_CLASS_PLUG_STATE,
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
            True,  # battery-status
            True,  # charge-mode
        ],
        "endpoints": {
            "battery_status": "battery_status_not_charging.json",
            "charge_mode": "charge_mode_schedule.json",
            "cockpit": "cockpit_ev.json",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                "entity_id": "binary_sensor.plugged_in",
                "unique_id": "vf1aaaaa555777999_plugged_in",
                "result": STATE_OFF,
                "class": DEVICE_CLASS_PLUG,
            },
            {
                "entity_id": "binary_sensor.charging",
                "unique_id": "vf1aaaaa555777999_charging",
                "result": STATE_OFF,
                "class": DEVICE_CLASS_BATTERY_CHARGING,
            },
        ],
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.battery_autonomy",
                "unique_id": "vf1aaaaa555777999_battery_autonomy",
                "result": "128",
                "unit": LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.battery_available_energy",
                "unique_id": "vf1aaaaa555777999_battery_available_energy",
                "result": "0",
                "unit": ENERGY_KILO_WATT_HOUR,
                "class": DEVICE_CLASS_ENERGY,
            },
            {
                "entity_id": "sensor.battery_level",
                "unique_id": "vf1aaaaa555777999_battery_level",
                "result": "50",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_BATTERY,
            },
            {
                "entity_id": "sensor.battery_temperature",
                "unique_id": "vf1aaaaa555777999_battery_temperature",
                "result": STATE_UNKNOWN,
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
            {
                "entity_id": "sensor.charge_mode",
                "unique_id": "vf1aaaaa555777999_charge_mode",
                "result": "schedule_mode",
                "class": DEVICE_CLASS_CHARGE_MODE,
            },
            {
                "entity_id": "sensor.charge_state",
                "unique_id": "vf1aaaaa555777999_charge_state",
                "result": "charge_error",
                "class": DEVICE_CLASS_CHARGE_STATE,
            },
            {
                "entity_id": "sensor.charging_power",
                "unique_id": "vf1aaaaa555777999_charging_power",
                "result": STATE_UNKNOWN,
                "unit": POWER_KILO_WATT,
                "class": DEVICE_CLASS_POWER,
            },
            {
                "entity_id": "sensor.charging_remaining_time",
                "unique_id": "vf1aaaaa555777999_charging_remaining_time",
                "result": STATE_UNKNOWN,
                "unit": TIME_MINUTES,
            },
            {
                "entity_id": "sensor.mileage",
                "unique_id": "vf1aaaaa555777999_mileage",
                "result": "49114",
                "unit": LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.plug_state",
                "unique_id": "vf1aaaaa555777999_plug_state",
                "result": "unplugged",
                "class": DEVICE_CLASS_PLUG_STATE,
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
            True,  # battery-status
            True,  # charge-mode
        ],
        "endpoints": {
            "battery_status": "battery_status_charging.json",
            "charge_mode": "charge_mode_always.json",
            "cockpit": "cockpit_fuel.json",
        },
        BINARY_SENSOR_DOMAIN: [
            {
                "entity_id": "binary_sensor.plugged_in",
                "unique_id": "vf1aaaaa555777123_plugged_in",
                "result": STATE_ON,
                "class": DEVICE_CLASS_PLUG,
            },
            {
                "entity_id": "binary_sensor.charging",
                "unique_id": "vf1aaaaa555777123_charging",
                "result": STATE_ON,
                "class": DEVICE_CLASS_BATTERY_CHARGING,
            },
        ],
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.battery_autonomy",
                "unique_id": "vf1aaaaa555777123_battery_autonomy",
                "result": "141",
                "unit": LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.battery_available_energy",
                "unique_id": "vf1aaaaa555777123_battery_available_energy",
                "result": "31",
                "unit": ENERGY_KILO_WATT_HOUR,
                "class": DEVICE_CLASS_ENERGY,
            },
            {
                "entity_id": "sensor.battery_level",
                "unique_id": "vf1aaaaa555777123_battery_level",
                "result": "60",
                "unit": PERCENTAGE,
                "class": DEVICE_CLASS_BATTERY,
            },
            {
                "entity_id": "sensor.battery_temperature",
                "unique_id": "vf1aaaaa555777123_battery_temperature",
                "result": "20",
                "unit": TEMP_CELSIUS,
                "class": DEVICE_CLASS_TEMPERATURE,
            },
            {
                "entity_id": "sensor.charge_mode",
                "unique_id": "vf1aaaaa555777123_charge_mode",
                "result": "always",
                "class": DEVICE_CLASS_CHARGE_MODE,
            },
            {
                "entity_id": "sensor.charge_state",
                "unique_id": "vf1aaaaa555777123_charge_state",
                "result": "charge_in_progress",
                "class": DEVICE_CLASS_CHARGE_STATE,
            },
            {
                "entity_id": "sensor.charging_power",
                "unique_id": "vf1aaaaa555777123_charging_power",
                "result": "27.0",
                "unit": POWER_KILO_WATT,
                "class": DEVICE_CLASS_POWER,
            },
            {
                "entity_id": "sensor.charging_remaining_time",
                "unique_id": "vf1aaaaa555777123_charging_remaining_time",
                "result": "145",
                "unit": TIME_MINUTES,
            },
            {
                "entity_id": "sensor.fuel_autonomy",
                "unique_id": "vf1aaaaa555777123_fuel_autonomy",
                "result": "35",
                "unit": LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.fuel_quantity",
                "unique_id": "vf1aaaaa555777123_fuel_quantity",
                "result": "3",
                "unit": VOLUME_LITERS,
            },
            {
                "entity_id": "sensor.mileage",
                "unique_id": "vf1aaaaa555777123_mileage",
                "result": "5567",
                "unit": LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.plug_state",
                "unique_id": "vf1aaaaa555777123_plug_state",
                "result": "plugged",
                "class": DEVICE_CLASS_PLUG_STATE,
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
            # Ignore,  # battery-status
            # Ignore,  # charge-mode
        ],
        "endpoints": {"cockpit": "cockpit_fuel.json"},
        BINARY_SENSOR_DOMAIN: [],
        SENSOR_DOMAIN: [
            {
                "entity_id": "sensor.fuel_autonomy",
                "unique_id": "vf1aaaaa555777123_fuel_autonomy",
                "result": "35",
                "unit": LENGTH_KILOMETERS,
            },
            {
                "entity_id": "sensor.fuel_quantity",
                "unique_id": "vf1aaaaa555777123_fuel_quantity",
                "result": "3",
                "unit": VOLUME_LITERS,
            },
            {
                "entity_id": "sensor.mileage",
                "unique_id": "vf1aaaaa555777123_mileage",
                "result": "5567",
                "unit": LENGTH_KILOMETERS,
            },
        ],
    },
}
