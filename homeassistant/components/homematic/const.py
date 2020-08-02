"""Constants for the homematic component."""

DOMAIN = "homematic"

DISCOVER_SWITCHES = "homematic.switch"
DISCOVER_LIGHTS = "homematic.light"
DISCOVER_SENSORS = "homematic.sensor"
DISCOVER_BINARY_SENSORS = "homematic.binary_sensor"
DISCOVER_COVER = "homematic.cover"
DISCOVER_CLIMATE = "homematic.climate"
DISCOVER_LOCKS = "homematic.locks"
DISCOVER_BATTERY = "homematic.battery"

ATTR_DISCOVER_DEVICES = "devices"
ATTR_PARAM = "param"
ATTR_CHANNEL = "channel"
ATTR_ADDRESS = "address"
ATTR_DEVICE_TYPE = "device_type"
ATTR_VALUE = "value"
ATTR_VALUE_TYPE = "value_type"
ATTR_INTERFACE = "interface"
ATTR_ERRORCODE = "error"
ATTR_MESSAGE = "message"
ATTR_TIME = "time"
ATTR_UNIQUE_ID = "unique_id"
ATTR_PARAMSET_KEY = "paramset_key"
ATTR_PARAMSET = "paramset"
ATTR_DISCOVERY_TYPE = "discovery_type"
ATTR_LOW_BAT = "LOW_BAT"
ATTR_LOWBAT = "LOWBAT"

EVENT_KEYPRESS = "homematic.keypress"
EVENT_IMPULSE = "homematic.impulse"
EVENT_ERROR = "homematic.error"

SERVICE_VIRTUALKEY = "virtualkey"
SERVICE_RECONNECT = "reconnect"
SERVICE_SET_VARIABLE_VALUE = "set_variable_value"
SERVICE_SET_DEVICE_VALUE = "set_device_value"
SERVICE_SET_INSTALL_MODE = "set_install_mode"
SERVICE_PUT_PARAMSET = "put_paramset"

HM_DEVICE_TYPES = {
    DISCOVER_SWITCHES: [
        "Switch",
        "SwitchPowermeter",
        "IOSwitch",
        "IPSwitch",
        "RFSiren",
        "IPSwitchPowermeter",
        "HMWIOSwitch",
        "Rain",
        "EcoLogic",
        "IPKeySwitchPowermeter",
        "IPGarage",
        "IPKeySwitch",
        "IPKeySwitchLevel",
        "IPMultiIO",
        "IPWSwitch",
    ],
    DISCOVER_LIGHTS: [
        "Dimmer",
        "KeyDimmer",
        "IPKeyDimmer",
        "IPDimmer",
        "ColorEffectLight",
        "IPKeySwitchLevel",
        "ColdWarmDimmer",
    ],
    DISCOVER_SENSORS: [
        "SwitchPowermeter",
        "Motion",
        "MotionV2",
        "RemoteMotion",
        "MotionIP",
        "ThermostatWall",
        "AreaThermostat",
        "RotaryHandleSensor",
        "WaterSensor",
        "PowermeterGas",
        "LuxSensor",
        "WeatherSensor",
        "WeatherStation",
        "ThermostatWall2",
        "TemperatureDiffSensor",
        "TemperatureSensor",
        "CO2Sensor",
        "IPSwitchPowermeter",
        "HMWIOSwitch",
        "FillingLevel",
        "ValveDrive",
        "EcoLogic",
        "IPThermostatWall",
        "IPSmoke",
        "RFSiren",
        "PresenceIP",
        "IPAreaThermostat",
        "IPWeatherSensor",
        "RotaryHandleSensorIP",
        "IPPassageSensor",
        "IPKeySwitchPowermeter",
        "IPThermostatWall230V",
        "IPWeatherSensorPlus",
        "IPWeatherSensorBasic",
        "IPBrightnessSensor",
        "IPGarage",
        "UniversalSensor",
        "MotionIPV2",
        "IPMultiIO",
        "IPThermostatWall2",
        "IPRemoteMotionV2",
        "HBUNISenWEA",
    ],
    DISCOVER_CLIMATE: [
        "Thermostat",
        "ThermostatWall",
        "MAXThermostat",
        "ThermostatWall2",
        "MAXWallThermostat",
        "IPThermostat",
        "IPThermostatWall",
        "ThermostatGroup",
        "IPThermostatWall230V",
        "IPThermostatWall2",
    ],
    DISCOVER_BINARY_SENSORS: [
        "ShutterContact",
        "Smoke",
        "SmokeV2",
        "Motion",
        "MotionV2",
        "MotionIP",
        "RemoteMotion",
        "WeatherSensor",
        "TiltSensor",
        "IPShutterContact",
        "HMWIOSwitch",
        "MaxShutterContact",
        "Rain",
        "WiredSensor",
        "PresenceIP",
        "IPWeatherSensor",
        "IPPassageSensor",
        "SmartwareMotion",
        "IPWeatherSensorPlus",
        "MotionIPV2",
        "WaterIP",
        "IPMultiIO",
        "TiltIP",
        "IPShutterContactSabotage",
        "IPContact",
        "IPRemoteMotionV2",
        "IPWInputDevice",
    ],
    DISCOVER_COVER: [
        "Blind",
        "KeyBlind",
        "IPKeyBlind",
        "IPKeyBlindTilt",
        "IPGarage",
        "IPKeyBlindMulti",
        "IPWKeyBlindMulti",
    ],
    DISCOVER_LOCKS: ["KeyMatic"],
}

HM_IGNORE_DISCOVERY_NODE = ["ACTUAL_TEMPERATURE", "ACTUAL_HUMIDITY"]

HM_IGNORE_DISCOVERY_NODE_EXCEPTIONS = {
    "ACTUAL_TEMPERATURE": [
        "IPAreaThermostat",
        "IPWeatherSensor",
        "IPWeatherSensorPlus",
        "IPWeatherSensorBasic",
        "IPThermostatWall",
        "IPThermostatWall2",
    ]
}

HM_ATTRIBUTE_SUPPORT = {
    "LOWBAT": ["battery", {0: "High", 1: "Low"}],
    "LOW_BAT": ["battery", {0: "High", 1: "Low"}],
    "ERROR": ["error", {0: "No"}],
    "ERROR_SABOTAGE": ["sabotage", {0: "No", 1: "Yes"}],
    "SABOTAGE": ["sabotage", {0: "No", 1: "Yes"}],
    "RSSI_PEER": ["rssi_peer", {}],
    "RSSI_DEVICE": ["rssi_device", {}],
    "VALVE_STATE": ["valve", {}],
    "LEVEL": ["level", {}],
    "BATTERY_STATE": ["battery", {}],
    "CONTROL_MODE": [
        "mode",
        {0: "Auto", 1: "Manual", 2: "Away", 3: "Boost", 4: "Comfort", 5: "Lowering"},
    ],
    "POWER": ["power", {}],
    "CURRENT": ["current", {}],
    "VOLTAGE": ["voltage", {}],
    "OPERATING_VOLTAGE": ["voltage", {}],
    "WORKING": ["working", {0: "No", 1: "Yes"}],
    "STATE_UNCERTAIN": ["state_uncertain", {}],
}

HM_PRESS_EVENTS = [
    "PRESS_SHORT",
    "PRESS_LONG",
    "PRESS_CONT",
    "PRESS_LONG_RELEASE",
    "PRESS",
]

HM_IMPULSE_EVENTS = ["SEQUENCE_OK"]

CONF_RESOLVENAMES_OPTIONS = ["metadata", "json", "xml", False]

DATA_HOMEMATIC = "homematic"
DATA_STORE = "homematic_store"
DATA_CONF = "homematic_conf"

CONF_INTERFACES = "interfaces"
CONF_LOCAL_IP = "local_ip"
CONF_LOCAL_PORT = "local_port"
CONF_PORT = "port"
CONF_PATH = "path"
CONF_CALLBACK_IP = "callback_ip"
CONF_CALLBACK_PORT = "callback_port"
CONF_RESOLVENAMES = "resolvenames"
CONF_JSONPORT = "jsonport"
