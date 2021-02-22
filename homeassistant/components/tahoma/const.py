"""Constants for the Somfy TaHoma integration."""
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.cover import DOMAIN as COVER
from homeassistant.components.light import DOMAIN as LIGHT
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
    "AdjustableSlatsRollerShutter": COVER,
    "AirFlowSensor": BINARY_SENSOR,  # widgetName, uiClass is AirSensor (sensor)
    "Awning": COVER,
    "CarButtonSensor": BINARY_SENSOR,
    "ContactSensor": BINARY_SENSOR,
    "Curtain": COVER,
    "DoorLock": LOCK,
    "ExteriorScreen": COVER,
    "ExteriorVenetianBlind": COVER,
    "GarageDoor": COVER,
    "Gate": COVER,
    "Light": LIGHT,
    "MotionSensor": BINARY_SENSOR,
    "MyFoxSecurityCamera": COVER,  # widgetName, uiClass is Camera (not supported)
    "OccupancySensor": BINARY_SENSOR,
    "Pergola": COVER,
    "RainSensor": BINARY_SENSOR,
    "RollerShutter": COVER,
    "Screen": COVER,
    "Shutter": COVER,
    "SirenStatus": BINARY_SENSOR,  # widgetName, uiClass is Siren (switch)
    "SmokeSensor": BINARY_SENSOR,
    "SwingingShutter": COVER,
    "VenetianBlind": COVER,
    "WaterDetectionSensor": BINARY_SENSOR,  # widgetName, uiClass is HumiditySensor (sensor)
    "Window": COVER,
    "WindowHandle": BINARY_SENSOR,
}

CORE_ON_OFF_STATE = "core:OnOffState"

COMMAND_OFF = "off"
COMMAND_ON = "on"

CONF_UPDATE_INTERVAL = "update_interval"
