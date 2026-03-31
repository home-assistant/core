"""Constants for the FortiOS Device Tracker integration."""

from datetime import timedelta

DOMAIN = "fortios"

DEFAULT_HOST = "192.168.1.1"
DEFAULT_VDOM = "root"
DEFAULT_PORT = 443
DEFAULT_VERIFY_SSL = False

SCAN_INTERVAL = timedelta(seconds=30)

CONF_VDOM = "vdom"
REST_TIMEOUT = 5
MINIMUM_SUPPORTED_VERSION = "6.4.3"

FORTIOS_RESULTS_MASTER_MAC = "master_mac"


DEFAULT_DEVICE_NAME = "Unknown entity"
# Icons
DEVICE_ICONS = {
    "android": "mdi:android",
    "ap": "mdi:access-point",
    "appliance": "mdi:chip",
    "automotive": "mdi:car",
    "color laserjet": "mdi:printer",
    "computer": "mdi:desktop-tower-monitor",
    "electric car": "mdi:car-electric",
    "fortiswitch": "mdi:switch",
    "home": "mdi:home",
    "homepod": "mdi:speaker",
    "ip camera": "mdi:cctv",
    "ip_phone": "mdi:phone-voip",
    "iphone": "mdi:cellphone",
    "laptop": "mdi:laptop",
    "mac": "mdi:apple",
    "multimedia_device": "mdi:play-network",
    "media player": "mdi:play-network",
    "nas": "mdi:nas",
    "networking_device": "mdi:network",
    "phone": "mdi:cellphone",
    "printer": "mdi:printer",
    "router": "mdi:router-wireless",
    "security system": "mdi:security",
    "sensor": "mdi:chip",
    "smart device": "mdi:chip",
    "smartphone": "mdi:cellphone",
    "switch": "mdi:switch",
    "tablet": "mdi:tablet",
    "television": "mdi:television",
    "thermostat": "mdi:thermostat",
    "tv": "mdi:television",
    "vg_console": "mdi:gamepad-variant",
    "virtual machine": "mdi:server",
    "voice control": "mdi:speaker-message",
    "watch": "mdi:watch",
    "wifi extender": "mdi:access-point",
    "workstation": "mdi:desktop-tower-monitor",
}
