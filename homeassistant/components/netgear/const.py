"""Netgear component constants."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "netgear"

PLATFORMS = [
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

CONF_CONSIDER_HOME = "consider_home"

KEY_ROUTER = "router"
KEY_COORDINATOR = "coordinator"
KEY_COORDINATOR_TRAFFIC = "coordinator_traffic"
KEY_COORDINATOR_SPEED = "coordinator_speed"
KEY_COORDINATOR_FIRMWARE = "coordinator_firmware"
KEY_COORDINATOR_UTIL = "coordinator_utilization"
KEY_COORDINATOR_LINK = "coordinator_link"

DEFAULT_CONSIDER_HOME = timedelta(seconds=180)
DEFAULT_NAME = "Netgear router"

MODE_ROUTER = "0"
MODE_AP = "1"

# models using port 80 instead of 5000
MODELS_PORT_80 = [
    "Orbi",
    "RBK",
    "RBR",
    "RBS",
    "RBW",
    "RS",
    "LBK",
    "LBR",
    "CBK",
    "CBR",
    "SRC",
    "SRK",
    "SRR",
    "SRS",
    "SXK",
    "SXR",
    "SXS",
]
PORT_80 = 80
MODELS_PORT_5555 = [
    "R7000",
]
PORT_5555 = 5555
# update method V2 models
MODELS_V2 = [
    "Orbi",
    "RBK",
    "RBR",
    "RBS",
    "RBW",
    "LBK",
    "LBR",
    "CBK",
    "CBR",
    "SRC",
    "SRK",
    "SRS",
    "SXK",
    "SXR",
    "SXS",
]

# Icons
DEVICE_ICONS = {
    0: "mdi:access-point-network",  # Router (Orbi ...)
    1: "mdi:book-open-variant",  # Amazon Kindle
    2: "mdi:android",  # Android Device
    3: "mdi:cellphone",  # Android Phone
    4: "mdi:tablet",  # Android Tablet
    5: "mdi:router-wireless",  # Apple Airport Express
    6: "mdi:disc-player",  # Blu-ray Player
    7: "mdi:router-network",  # Bridge
    8: "mdi:play-network",  # Cable STB
    9: "mdi:camera",  # Camera
    10: "mdi:router-network",  # Router
    11: "mdi:play-network",  # DVR
    12: "mdi:gamepad-variant",  # Gaming Console
    13: "mdi:monitor",  # iMac
    14: "mdi:tablet",  # iPad
    15: "mdi:tablet",  # iPad Mini
    16: "mdi:cellphone",  # iPhone 5/5S/5C
    17: "mdi:cellphone",  # iPhone
    18: "mdi:ipod",  # iPod Touch
    19: "mdi:linux",  # Linux PC
    20: "mdi:apple-finder",  # Mac Mini
    21: "mdi:desktop-tower",  # Mac Pro
    22: "mdi:laptop",  # MacBook
    23: "mdi:play-network",  # Media Device
    24: "mdi:network",  # Network Device
    25: "mdi:play-network",  # Other STB
    26: "mdi:power-plug",  # Powerline
    27: "mdi:printer",  # Printer
    28: "mdi:access-point",  # Repeater
    29: "mdi:play-network",  # Satellite STB
    30: "mdi:scanner",  # Scanner
    31: "mdi:play-network",  # SlingBox
    32: "mdi:cellphone",  # Smart Phone
    33: "mdi:nas",  # Storage (NAS)
    34: "mdi:switch",  # Switch
    35: "mdi:television",  # TV
    36: "mdi:tablet",  # Tablet
    37: "mdi:desktop-classic",  # UNIX PC
    38: "mdi:desktop-tower-monitor",  # Windows PC
    39: "mdi:laptop",  # Surface
    40: "mdi:access-point-network",  # Wifi Extender
    41: "mdi:cast-variant",  # Apple TV
}
