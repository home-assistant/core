"""Constants for the BSB-Lan integration."""
# from homeassistant.const import CONF_ICON, CONF_NAME, CONF_TYPE

DOMAIN = "bsblan"

DATA_BSBLAN_CLIENT = "bsblan_client"
DATA_BSBLAN_TIMER = "bsblan_timer"
DATA_BSBLAN_UPDATED = "bsblan_updated"

ATTR_IDENTIFIERS = "identifiers"
ATTR_MODEL = "model"
ATTR_MANUFACTURER = "manufacturer"

ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_INSIDE_TEMPERATURE = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE = "outside_temperature"

ATTR_STATE_ON = "on"
ATTR_STATE_OFF = "off"

CONF_DEVICE_IDENT = "device_identification="

SENSOR_TYPE_TEMPERATURE = "temperature"

# SENSOR_TYPES = {
#     ATTR_INSIDE_TEMPERATURE: {
#         CONF_NAME: "Inside Temperature",
#         CONF_ICON: "mdi:thermometer",
#         CONF_TYPE: SENSOR_TYPE_TEMPERATURE,
#     },
#     ATTR_OUTSIDE_TEMPERATURE: {
#         CONF_NAME: "Outside Temperature",
#         CONF_ICON: "mdi:thermometer",
#         CONF_TYPE: SENSOR_TYPE_TEMPERATURE,
#     },
# }
