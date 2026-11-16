"""Constants for the HomematicIP Cloud integration."""

from homematicip.base.enums import DeviceType, FunctionalChannelType

from homeassistant.const import Platform

DOMAIN = "homematicip_cloud"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VALVE,
    Platform.WEATHER,
]

MODE_AWAY = "away"
MODE_HOME = "home"
SIGNAL_ARMING_BLOCKED = f"{DOMAIN}_arming_blocked_{{}}"

CONF_ACCESSPOINT = "accesspoint"
CONF_AUTHTOKEN = "authtoken"

HMIPC_NAME = "name"
HMIPC_HAPID = "hapid"
HMIPC_AUTHTOKEN = "authtoken"
HMIPC_PIN = "pin"

SWITCH_CHANNEL_TYPES = (
    FunctionalChannelType.SWITCH_CHANNEL,
    FunctionalChannelType.SWITCH_MEASURING_CHANNEL,
    FunctionalChannelType.MULTI_MODE_INPUT_SWITCH_CHANNEL,
)

# these carry a switch channel, but their entity is a light
LIGHT_OWNED_DEVICE_TYPES = (
    DeviceType.BRAND_SWITCH_NOTIFICATION_LIGHT,
    DeviceType.BRAND_SWITCH_MEASURING,
)
