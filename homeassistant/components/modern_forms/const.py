"""Constants for the Modern Forms integration."""

DOMAIN = "modern_forms"

ATTR_IDENTIFIERS = "identifiers"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"
ATTR_OWNER = "owner"
ATTR_IDENTITY = "identity"
ATTR_MCU_FIRMWARE_VERSION = "mcu_firmware_version"
ATTR_FIRMWARE_VERSION = "firmware_version"

SIGNAL_INSTANCE_ADD = f"{DOMAIN}_instance_add_signal." "{}"
SIGNAL_INSTANCE_REMOVE = f"{DOMAIN}_instance_remove_signal." "{}"
SIGNAL_ENTITY_REMOVE = f"{DOMAIN}_entity_remove_signal." "{}"

CONF_ON_UNLOAD = "ON_UNLOAD"

OPT_BRIGHTNESS = "brightness"
OPT_ON = "on"
OPT_SPEED = "speed"

# Services
SERVICE_SET_LIGHT_SLEEP_TIMER = "set_light_sleep_timer"
SERVICE_CLEAR_LIGHT_SLEEP_TIMER = "clear_light_sleep_timer"
SERVICE_SET_FAN_SLEEP_TIMER = "set_fan_sleep_timer"
SERVICE_CLEAR_FAN_SLEEP_TIMER = "clear_fan_sleep_timer"

ATTR_SLEEP_TIME = "sleep_time"
CLEAR_TIMER = 0
