"""Constants for EBUS integration."""
from datetime import timedelta

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
PRIO_TIMEDELTAS = [timedelta(hours=1), timedelta(hours=4), timedelta(days=1)]
SCAN = "scan"

CONF_CIRCUITINFOS = "circuitinfos"
CONF_CIRCUITMAP = "circuitmap"
CONF_MSGDEFCODES = "msgdefcodes"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "8888"
DEFAULT_PRIO = 4
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

SERVICE_SETVALUE = "set_value"
SERVICES = [
    SERVICE_SETVALUE,
]
