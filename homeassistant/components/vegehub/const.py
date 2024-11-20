"""Constants for the Vegetronix VegeHub integration."""

from homeassistant.const import Platform

DOMAIN = "vegehub"
NAME = "VegeHub"
PLATFORMS = [Platform.SENSOR]
MANUFACTURER = "vegetronix"
MODEL = "VegeHub"
OPTION_DATA_TYPE_CHOICES = [
    "Raw Voltage",
    "VH400",
    "THERM200",
]
CHAN_TYPE_SENSOR = "sensor"
CHAN_TYPE_ACTUATOR = "actuator"
CHAN_TYPE_BATTERY = "battery"
API_PATH = "/api/vegehub/update"
