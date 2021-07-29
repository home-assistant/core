"""Const for TP-Link."""
import datetime

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.components.switch import ATTR_CURRENT_POWER_W, ATTR_TODAY_ENERGY_KWH
from homeassistant.const import (
    ATTR_VOLTAGE,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)

DOMAIN = "tplink"
COORDINATORS = "coordinators"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=8)
MAX_DISCOVERY_RETRIES = 4

ATTR_CONFIG = "config"
ATTR_TOTAL_ENERGY_KWH = "total_energy_kwh"
ATTR_CURRENT_A = "current_a"

CONF_MODEL = "model"
CONF_SW_VERSION = "sw_ver"
CONF_EMETER_PARAMS = "emeter_params"
CONF_DIMMER = "dimmer"
CONF_DISCOVERY = "discovery"
CONF_LIGHT = "light"
CONF_STRIP = "strip"
CONF_SWITCH = "switch"
CONF_SENSOR = "sensor"

PLATFORMS = [CONF_LIGHT, CONF_SENSOR, CONF_SWITCH]

ENERGY_SENSORS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=ATTR_CURRENT_POWER_W,
        unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Current Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_KWH,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        name="Total Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_TODAY_ENERGY_KWH,
        unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        name="Today's Consumption",
    ),
    SensorEntityDescription(
        key=ATTR_VOLTAGE,
        unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Voltage",
    ),
    SensorEntityDescription(
        key=ATTR_CURRENT_A,
        unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        name="Current",
    ),
]
