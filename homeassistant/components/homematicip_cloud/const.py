"""Constants for the HomematicIP Cloud integration."""

from homeassistant.const import Platform

DOMAIN = "homematicip_cloud"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VALVE,
    Platform.WEATHER,
]

ATTR_BLOCKING_DEVICES = "blocking_devices"
SIGNAL_ARMING_PROBLEMS = f"{DOMAIN}_arming_problems_{{}}"

CONF_ACCESSPOINT = "accesspoint"
CONF_AUTHTOKEN = "authtoken"

HMIPC_NAME = "name"
HMIPC_HAPID = "hapid"
HMIPC_AUTHTOKEN = "authtoken"
HMIPC_PIN = "pin"
