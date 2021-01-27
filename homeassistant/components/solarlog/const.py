"""Constants for the Solar-Log integration."""
from datetime import timedelta

from homeassistant.const import ENERGY_KILO_WATT_HOUR, PERCENTAGE, POWER_WATT, VOLT

DOMAIN = "solarlog"

"""Default config for solarlog."""
DEFAULT_HOST = "http://solar-log"
DEFAULT_NAME = "solarlog"

"""Fixed constants."""
SCAN_INTERVAL = timedelta(seconds=60)

"""Supported sensor types."""
SENSOR_TYPES = {
    "time": ["TIME", "last update", None, "mdi:calendar-clock"],
    "power_ac": ["powerAC", "power AC", POWER_WATT, "mdi:solar-power"],
    "power_dc": ["powerDC", "power DC", POWER_WATT, "mdi:solar-power"],
    "voltage_ac": ["voltageAC", "voltage AC", VOLT, "mdi:flash"],
    "voltage_dc": ["voltageDC", "voltage DC", VOLT, "mdi:flash"],
    "yield_day": ["yieldDAY", "yield day", ENERGY_KILO_WATT_HOUR, "mdi:solar-power"],
    "yield_yesterday": [
        "yieldYESTERDAY",
        "yield yesterday",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "yield_month": [
        "yieldMONTH",
        "yield month",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "yield_year": ["yieldYEAR", "yield year", ENERGY_KILO_WATT_HOUR, "mdi:solar-power"],
    "yield_total": [
        "yieldTOTAL",
        "yield total",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_ac": ["consumptionAC", "consumption AC", POWER_WATT, "mdi:power-plug"],
    "consumption_day": [
        "consumptionDAY",
        "consumption day",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
    ],
    "consumption_yesterday": [
        "consumptionYESTERDAY",
        "consumption yesterday",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
    ],
    "consumption_month": [
        "consumptionMONTH",
        "consumption month",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
    ],
    "consumption_year": [
        "consumptionYEAR",
        "consumption year",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
    ],
    "consumption_total": [
        "consumptionTOTAL",
        "consumption total",
        ENERGY_KILO_WATT_HOUR,
        "mdi:power-plug",
    ],
    "total_power": ["totalPOWER", "total power", "Wp", "mdi:solar-power"],
    "alternator_loss": [
        "alternatorLOSS",
        "alternator loss",
        POWER_WATT,
        "mdi:solar-power",
    ],
    "capacity": ["CAPACITY", "capacity", PERCENTAGE, "mdi:solar-power"],
    "efficiency": [
        "EFFICIENCY",
        "efficiency",
        f"% {POWER_WATT}/{POWER_WATT}p",
        "mdi:solar-power",
    ],
    "power_available": [
        "powerAVAILABLE",
        "power available",
        POWER_WATT,
        "mdi:solar-power",
    ],
    "usage": ["USAGE", "usage", None, "mdi:solar-power"],
}
