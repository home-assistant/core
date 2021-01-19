"""Constants for EBUS integration."""
DOMAIN = "ebus"
API = "api"
UNDO_UPDATE_LISTENER = "undo_update_listener"
UNIT_DEVICE_CLASS_MAP = {
    "°C": "temperature",
    "°F": "temperature",
    "W": "power",
    "kW": "power",
    "hPa": "pressure",
    "mbar": "pressure",
    "bar": "pressure",
    "A": "current",
    "Wh": "energy",
    "kWh": "energy",
    "V": "voltage",
}
TTL = 30000
CHECKINTERVAL = 60
TIMEOUT = 5

CONF_MSGDEFCODES = "msgdefcodes"
CONF_CIRCUITMAP = "circuitmap"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "8888"
DEFAULT_CIRCUITMAP = {
    "broadcast": "",
    "ui": "UI",
    "bai": "Heater",
    "bc": "Burner",
    "hc": "Heating",
    "mc": "Mixer",
    "hwc": "Water",
    "cc": "Circulation",
    "sc": "Solar",
}
