"""Constants for the Vegetronix VegeHub integration."""

from homeassistant.const import Platform

DOMAIN = "vegehub"
NAME = "VegeHub"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH]
MANUFACTURER = "vegetronix"
MODEL = "VegeHub"
OPTION_DATA_TYPE_CHOICES = [
    "Raw Voltage",
    "VH400",
    "THERM200",
]
