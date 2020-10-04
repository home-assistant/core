"""Constants for the TaHoma integration."""
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_CONTROL_PANEL
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.components.cover import DOMAIN as COVER
from homeassistant.components.light import DOMAIN as LIGHT
from homeassistant.components.lock import DOMAIN as LOCK
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH

DOMAIN = "tahoma"

MIN_UPDATE_INTERVAL = 1
DEFAULT_UPDATE_INTERVAL = 30

IGNORED_TAHOMA_TYPES = [
    "ProtocolGateway",
    "Pod",
]

# Used to map the Somfy widget and ui_class to the Home Assistant platform
TAHOMA_TYPES = {
    "AdjustableSlatsRollerShutter": COVER,
    "AirFlowSensor": BINARY_SENSOR,  # widgetName, uiClass is AirSensor (sensor)
    "AirSensor": SENSOR,
    "Alarm": ALARM_CONTROL_PANEL,
    "AtlanticElectricalHeater": CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    "Awning": COVER,
    "CarButtonSensor": BINARY_SENSOR,
    "ConsumptionSensor": SENSOR,
    "ContactSensor": BINARY_SENSOR,
    "Curtain": COVER,
    "DimmerExteriorHeating": CLIMATE,  # widgetName, uiClass is ExteriorHeatingSystem (not supported)
    "DomesticHotWaterTank": SWITCH,  # widgetName, uiClass is WaterHeatingSystem (not supported)
    "DoorLock": LOCK,
    "ElectricitySensor": SENSOR,
    "ExteriorScreen": COVER,
    "ExteriorVenetianBlind": COVER,
    "GarageDoor": COVER,
    "GasSensor": SENSOR,
    "Gate": COVER,
    "Generic": COVER,
    "GenericSensor": SENSOR,
    "HumiditySensor": SENSOR,
    "Light": LIGHT,
    "LightSensor": SENSOR,
    "MotionSensor": BINARY_SENSOR,
    "MyFoxSecurityCamera": COVER,  # widgetName, uiClass is Camera (not supported)
    "OccupancySensor": BINARY_SENSOR,
    "OnOff": SWITCH,
    "Pergola": COVER,
    "RainSensor": BINARY_SENSOR,
    "RollerShutter": COVER,
    "Screen": COVER,
    "Shutter": COVER,
    "Siren": SWITCH,
    "SirenStatus": BINARY_SENSOR,  # widgetName, uiClass is Siren (switch)
    "SmokeSensor": BINARY_SENSOR,
    "SomfyThermostat": CLIMATE,  # widgetName, uiClass is HeatingSystem (not supported)
    "StatelessExteriorHeating": CLIMATE,  # widgetName, uiClass is ExteriorHeatingSystem.
    "SunIntensitySensor": SENSOR,
    "SunSensor": SENSOR,
    "SwimmingPool": SWITCH,
    "SwingingShutter": COVER,
    "TemperatureSensor": SENSOR,
    "ThermalEnergySensor": SENSOR,
    "VenetianBlind": COVER,
    "WaterDetectionSensor": BINARY_SENSOR,  # widgetName, uiClass is HumiditySensor (sensor)
    "WaterSensor": SENSOR,
    "WeatherSensor": SENSOR,
    "WindSensor": SENSOR,
    "Window": COVER,
    "WindowHandle": BINARY_SENSOR,
}

CORE_ON_OFF_STATE = "core:OnOffState"

COMMAND_OFF = "off"
COMMAND_ON = "on"

CONF_UPDATE_INTERVAL = "update_interval"
