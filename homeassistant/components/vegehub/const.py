"""Constants for the Vegetronix VegeHub integration."""

DOMAIN = "vegehub"
CONF_API_KEY = "api_key"
METHODS = ["POST"]
PLATFORMS = ["sensor", "switch"]
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
