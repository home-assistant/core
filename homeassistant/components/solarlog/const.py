"""Constants for the Solar-Log integration."""
from datetime import timedelta

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)

DOMAIN = "solarlog"

"""Default config for solarlog."""
DEFAULT_HOST = "http://solar-log"
DEFAULT_NAME = "solarlog"

"""Fixed constants."""
SCAN_INTERVAL = timedelta(seconds=60)

"""Supported sensor types."""
# key: [json_key, label, unit_of_measurement, icon, state_class, device_class]
SENSOR_TYPES = {
    "time": [
        "TIME",
        "last update",
        None,
        "mdi:calendar-clock",
        None,
        DEVICE_CLASS_TIMESTAMP,
    ],
    "power_ac": [
        "powerAC",
        "power AC",
        POWER_WATT,
        "mdi:solar-power",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_POWER,
    ],
    "power_dc": [
        "powerDC",
        "power DC",
        POWER_WATT,
        "mdi:solar-power",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_POWER,
    ],
    "voltage_ac": [
        "voltageAC",
        "voltage AC",
        ELECTRIC_POTENTIAL_VOLT,
        "mdi:flash",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_VOLTAGE,
    ],
    "voltage_dc": [
        "voltageDC",
        "voltage DC",
        ELECTRIC_POTENTIAL_VOLT,
        "mdi:flash",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_VOLTAGE,
    ],
    "yield_day": [
        "yieldDAY",
        "yield day",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_ENERGY,
    ],
    "yield_yesterday": [
        "yieldYESTERDAY",
        "yield yesterday",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
        None,
        DEVICE_CLASS_ENERGY,
    ],
    "yield_month": [
        "yieldMONTH",
        "yield month",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
        None,
        DEVICE_CLASS_ENERGY,
    ],
    "yield_year": [
        "yieldYEAR",
        "yield year",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
        None,
        DEVICE_CLASS_ENERGY,
    ],
    "yield_total": [
        "yieldTOTAL",
        "yield total",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
        None,
        DEVICE_CLASS_ENERGY,
    ],
    "consumption_ac": [
        "consumptionAC",
        "consumption AC",
        POWER_WATT,
        "mdi:power-plug",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_POWER,
    ],
    "consumption_day": [
        "consumptionDAY",
        "consumption day",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_ENERGY,
    ],
    "consumption_yesterday": [
        "consumptionYESTERDAY",
        "consumption yesterday",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
        None,
        DEVICE_CLASS_ENERGY,
    ],
    "consumption_month": [
        "consumptionMONTH",
        "consumption month",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
        None,
        DEVICE_CLASS_ENERGY,
    ],
    "consumption_year": [
        "consumptionYEAR",
        "consumption year",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
        None,
        DEVICE_CLASS_ENERGY,
    ],
    "consumption_total": [
        "consumptionTOTAL",
        "consumption total",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
        None,
        DEVICE_CLASS_ENERGY,
    ],
    "total_power": [
        "totalPOWER",
        "total power",
        "Wp",
        "mdi:solar-power",
        None,
        None,
    ],
    "alternator_loss": [
        "alternatorLOSS",
        "alternator loss",
        POWER_WATT,
        "mdi:solar-power",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_POWER,
    ],
    "capacity": [
        "CAPACITY",
        "capacity",
        PERCENTAGE,
        "mdi:solar-power",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_POWER_FACTOR,
    ],
    "efficiency": [
        "EFFICIENCY",
        "efficiency",
        f"% {POWER_WATT}/{POWER_WATT}p",
        "mdi:solar-power",
        STATE_CLASS_MEASUREMENT,
        None,
    ],
    "power_available": [
        "powerAVAILABLE",
        "power available",
        POWER_WATT,
        "mdi:solar-power",
        STATE_CLASS_MEASUREMENT,
        DEVICE_CLASS_POWER,
    ],
    "usage": [
        "USAGE",
        "usage",
        None,
        "mdi:solar-power",
        STATE_CLASS_MEASUREMENT,
        None,
    ],
}
