"""Constants for the Somfy TaHoma integration."""
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.lock import DOMAIN as LOCK

DOMAIN = "tahoma"

MIN_UPDATE_INTERVAL = 30
DEFAULT_UPDATE_INTERVAL = 30

IGNORED_TAHOMA_TYPES = [
    "ProtocolGateway",
    "Pod",
]

# Used to map the Somfy widget and ui_class to the Home Assistant platform
TAHOMA_TYPES = {
    "AirFlowSensor": BINARY_SENSOR,  # widgetName, uiClass is AirSensor (sensor)
    "CarButtonSensor": BINARY_SENSOR,
    "ContactSensor": BINARY_SENSOR,
    "DoorLock": LOCK,
    "MotionSensor": BINARY_SENSOR,
    "OccupancySensor": BINARY_SENSOR,
    "RainSensor": BINARY_SENSOR,
    "SirenStatus": BINARY_SENSOR,  # widgetName, uiClass is Siren (switch)
    "SmokeSensor": BINARY_SENSOR,
    "WaterDetectionSensor": BINARY_SENSOR,  # widgetName, uiClass is HumiditySensor (sensor)
    "WindowHandle": BINARY_SENSOR,
}

CORE_ON_OFF_STATE = "core:OnOffState"

COMMAND_OFF = "off"
COMMAND_ON = "on"

CONF_UPDATE_INTERVAL = "update_interval"
