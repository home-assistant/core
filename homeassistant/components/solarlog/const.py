"""Constants for the Solar-Log integration."""
from datetime import timedelta

from homeassistant.const import POWER_WATT, ENERGY_KILO_WATT_HOUR

DOMAIN = "solarlog"

"""Default config for solarlog."""
DEFAULT_HOST = "solar-log"
DEFAULT_NAME = "solarlog"

"""Fixed constants."""
SCAN_INTERVAL = timedelta(seconds=60)

"""Supported sensor types."""
SENSOR_TYPES = {
    "time": ["TIME", "last update", None, "mdi:solar-power"],
    "power_ac": ["powerAC", "power AC", POWER_WATT, "mdi:solar-power"],
    "power_dc": ["powerDC", "power DC", POWER_WATT, "mdi:solar-power"],
    "voltage_ac": ["voltageAC", "voltage AC", "V", "mdi:solar-power"],
    "voltage_dc": ["voltageDC", "voltage DC", "V", "mdi:solar-power"],
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
    "consumption_ac": [
        "consumptionAC",
        "consumption AC",
        POWER_WATT,
        "mdi:solar-power",
    ],
    "consumption_day": [
        "consumptionDAY",
        "consumption day",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_yesterday": [
        "consumptionYESTERDAY",
        "consumption yesterday",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_month": [
        "consumptionMONTH",
        "consumption month",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_year": [
        "consumptionYEAR",
        "consumption year",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "consumption_total": [
        "consumptionTOTAL",
        "consumption total",
        ENERGY_KILO_WATT_HOUR,
        "mdi:solar-power",
    ],
    "total_power": ["totalPOWER", "total power", "Wp", "mdi:solar-power"],
    "alternator_loss": [
        "alternatorLOSS",
        "alternator loss",
        POWER_WATT,
        "mdi:solar-power",
    ],
    "capacity": ["CAPACITY", "capacity", "%", "mdi:solar-power"],
    "efficiency": ["EFFICIENCY", "efficiency", "% W/Wp", "mdi:solar-power"],
    "power_available": [
        "powerAVAILABLE",
        "power available",
        POWER_WATT,
        "mdi:solar-power",
    ],
    "usage": ["USAGE", "usage", None, "mdi:solar-power"],
}
