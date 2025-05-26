"""Alexa Devices constants."""

import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "alexa_devices"
CONF_LOGIN_DATA = "login_data"

# Services variables
ATTR_TEXT_COMMAND = "text_command"
ATTR_SOUND = "sound"
SERVICE_TEXT_COMMAND = "send_text_command"
SERVICE_SOUND_NOTIFICATION = "send_sound"
