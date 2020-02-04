"""Constants for the Luxtronik integration."""
from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TIMESTAMP,
    ENERGY_KILO_WATT_HOUR,
    PRESSURE_BAR,
    TEMP_CELSIUS,
)

ATTR_PARAMETER = "parameter"
ATTR_VALUE = "value"

CONF_INVERT_STATE = "invert"
CONF_SAFE = "safe"
CONF_GROUP = "group"
CONF_PARAMETERS = "parameters"
CONF_CALCULATIONS = "calculations"
CONF_VISIBILITIES = "visibilities"
CONF_CELSIUS = "celsius"
CONF_SECONDS = "seconds"
CONF_TIMESTAMP = "timestamp"
CONF_KELVIN = "kelvin"
CONF_BAR = "bar"
CONF_PERCENT = "percent"
CONF_ENERGY = "energy"
CONF_VOLTAGE = "voltage"
CONF_HOURS = "hours"
CONF_FLOW = "flow"

TIME_SECONDS = "s"
TIME_HOUR = "h"
TEMP_KELVIN = "K"
PERCENTAGE_PERCENT = "%"
VOLTAGE_VOLT = "V"
FLOW_LITERS_PER_MINUTE = "l/min"

ICONS = {
    "celsius": "mdi:thermometer",
    "seconds": "mdi:timer-sand",
    "pulses": "mdi:pulse",
    "ipaddress": "mdi:ip-network-outline",
    "timestamp": "mdi:calendar-range",
    "errorcode": "mdi:alert-circle-outline",
    "kelvin": "mdi:thermometer",
    "bar": "mdi:arrow-collapse-all",
    "percent": "mdi:percent",
    "rpm": "mdi:rotate-right",
    "energy": "mdi:flash-circle",
    "voltage": "mdi:flash-outline",
    "hours": "mdi:clock-outline",
    "flow": "mdi:chart-bell-curve",
    "level": "mdi:format-list-numbered",
    "count": "mdi:counter",
    "version": "mdi:information-outline",
}

DEVICE_CLASSES = {
    CONF_CELSIUS: DEVICE_CLASS_PRESSURE,
    CONF_KELVIN: DEVICE_CLASS_PRESSURE,
    CONF_BAR: DEVICE_CLASS_PRESSURE,
    CONF_SECONDS: DEVICE_CLASS_TIMESTAMP,
    CONF_HOURS: DEVICE_CLASS_TIMESTAMP,
    CONF_TIMESTAMP: DEVICE_CLASS_TIMESTAMP,
}

UNITS = {
    CONF_CELSIUS: TEMP_CELSIUS,
    CONF_SECONDS: TIME_SECONDS,
    CONF_KELVIN: TEMP_KELVIN,
    CONF_BAR: PRESSURE_BAR,
    CONF_PERCENT: PERCENTAGE_PERCENT,
    CONF_ENERGY: ENERGY_KILO_WATT_HOUR,
    CONF_VOLTAGE: VOLTAGE_VOLT,
    CONF_HOURS: TIME_HOUR,
    CONF_FLOW: FLOW_LITERS_PER_MINUTE,
}
