"""Constants for the Solar-Log integration."""
from datetime import timedelta
from typing import Final

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
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
SENSORS: Final[list[SensorEntityDescription]] = [
    SensorEntityDescription(
        key="time",
        name="last update",
        icon="mdi:calendar-clock",
        device_class=DEVICE_CLASS_TIMESTAMP,
    ),
    SensorEntityDescription(
        key="power_ac",
        name="power AC",
        icon="mdi:solar-power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_dc",
        name="power DC",
        icon="mdi:solar-power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_ac",
        name="voltage AC",
        icon="mdi:flash",
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_dc",
        name="voltage DC",
        icon="mdi:flash",
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="yield_day",
        name="yield day",
        icon="mdi:solar-power",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="yield_yesterday",
        name="yield yesterday",
        icon="mdi:solar-power",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="yield_month",
        name="yield month",
        icon="mdi:solar-power",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="yield_year",
        name="yield year",
        icon="mdi:solar-power",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="yield_total",
        name="yield total",
        icon="mdi:solar-power",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="consumption_ac",
        name="consumption AC",
        icon="mdi:power-plug",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="consumption_day",
        name="consumption day",
        icon="mdi:power-plug",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="consumption_yesterday",
        name="consumption yesterday",
        icon="mdi:power-plug",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="consumption_month",
        name="consumption month",
        icon="mdi:power-plug",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="consumption_year",
        name="consumption year",
        icon="mdi:power-plug",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="consumption_total",
        name="consumption total",
        icon="mdi:power-plug",
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
    ),
    SensorEntityDescription(
        key="total_power",
        name="total power",
        icon="mdi:power-plug",
        unit_of_measurement="Wp",
    ),
    SensorEntityDescription(
        key="alternator_loss",
        name="alternator loss",
        icon="mdi:solar-power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="capacity",
        name="capacity",
        icon="mdi:solar-power",
        unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_POWER_FACTOR,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="efficiency",
        name="efficiency",
        icon="mdi:solar-power",
        unit_of_measurement=f"% {POWER_WATT}/{POWER_WATT}p",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_available",
        name="power available",
        icon="mdi:solar-power",
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="usage",
        name="usage",
        icon="mdi:solar-power",
        state_class=STATE_CLASS_MEASUREMENT,
    ),
]

API_DICT = {
    "time": "TIME",
    "power_ac": "powerAC",
    "power_dc": "powerDC",
    "voltage_ac": "voltageAC",
    "voltage_dc": "voltageDC",
    "yield_day": "yieldDAY",
    "yield_yesterday": "yieldYESTERDAY",
    "yield_month": "yieldMONTH",
    "yield_year": "yieldYEAR",
    "yield_total": "yieldTOTAL",
    "consumption_ac": "consumptionAC",
    "consumption_day": "consumptionDAY",
    "consumption_yesterday": "consumptionYESTERDAY",
    "consumption_month": "consumptionMONTH",
    "consumption_year": "consumptionYEAR",
    "consumption_total": "consumptionTOTAL",
    "total_power": "totalPOWER",
    "alternator_loss": "alternatorLOSS",
    "capacity": "CAPACITY",
    "efficiency": "EFFICIENCY",
    "power_available": "powerAVAILABLE",
    "usage": "USAGE",
}
