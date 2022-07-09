"""Constants for the BleBox devices integration."""

from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import TEMP_CELSIUS

DOMAIN = "blebox"
PRODUCT = "product"

DEFAULT_SETUP_TIMEOUT = 10

# translation strings
ADDRESS_ALREADY_CONFIGURED = "address_already_configured"
CANNOT_CONNECT = "cannot_connect"
UNSUPPORTED_VERSION = "unsupported_version"
UNKNOWN = "unknown"

BLEBOX_TO_HASS_DEVICE_CLASSES = {
    "shutter": CoverDeviceClass.SHUTTER,
    "gatebox": CoverDeviceClass.DOOR,
    "gate": CoverDeviceClass.GATE,
    "relay": SwitchDeviceClass.SWITCH,
    "temperature": SensorDeviceClass.TEMPERATURE,
}


BLEBOX_TO_UNIT_MAP = {"celsius": TEMP_CELSIUS}

DEFAULT_HOST = "192.168.0.2"
DEFAULT_PORT = 80
