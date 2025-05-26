"""Alexa Devices constants."""

import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "alexa_devices"
CONF_LOGIN_DATA = "login_data"

# Services variables
ATTR_CMD = "cmd"
ATTR_SOUND = "sound"
SERVICE_CUSTOM_COMMAND = "send_custom"
SERVICE_SOUND_NOTIFICATION = "send_sound"
