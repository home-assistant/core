"""Constants for Daikin."""
from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE

ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_INSIDE_TEMPERATURE = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"
ATTR_TOTAL_POWER = "total_power"
ATTR_COOL_ENERGY = "cool_energy"
ATTR_HEAT_ENERGY = "heat_energy"

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"

SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_POWER = "power"
SENSOR_TYPE_ENERGY = "energy"

SENSOR_TYPES = {
    ATTR_INSIDE_TEMPERATURE: {
        CONF_NAME: "Inside Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_TYPE: SENSOR_TYPE_TEMPERATURE,
    },
    ATTR_OUTSIDE_TEMPERATURE: {
        CONF_NAME: "Outside Temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_TYPE: SENSOR_TYPE_TEMPERATURE,
    },
    ATTR_TOTAL_POWER: {
        CONF_NAME: "Total Power Consumption",
        CONF_ICON: "mdi:flash",
        CONF_TYPE: SENSOR_TYPE_POWER,
    },
    ATTR_COOL_ENERGY: {
        CONF_NAME: "Cool Energy Consumption",
        CONF_ICON: "mdi:snowflake",
        CONF_TYPE: SENSOR_TYPE_ENERGY,
    },
    ATTR_HEAT_ENERGY: {
        CONF_NAME: "Heat Power Consumption",
        CONF_ICON: "mdi:fire",
        CONF_TYPE: SENSOR_TYPE_ENERGY,
    },
}

CONF_KEY = "key"
CONF_UUID = "uuid"

KEY_MAC = "mac"
KEY_IP = "ip"

TIMEOUT = 60
