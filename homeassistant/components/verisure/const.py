"""Constants for the Verisure integration."""
from datetime import timedelta
import logging

DOMAIN = "verisure"

LOGGER = logging.getLogger(__package__)

ATTR_DEVICE_SERIAL = "device_serial"

CONF_ALARM = "alarm"
CONF_CODE_DIGITS = "code_digits"
CONF_DOOR_WINDOW = "door_window"
CONF_GIID = "giid"
CONF_HYDROMETERS = "hygrometers"
CONF_LOCKS = "locks"
CONF_DEFAULT_LOCK_CODE = "default_lock_code"
CONF_MOUSE = "mouse"
CONF_SMARTPLUGS = "smartplugs"
CONF_THERMOMETERS = "thermometers"
CONF_SMARTCAM = "smartcam"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)
MIN_SCAN_INTERVAL = timedelta(minutes=1)

SERVICE_CAPTURE_SMARTCAM = "capture_smartcam"
SERVICE_DISABLE_AUTOLOCK = "disable_autolock"
SERVICE_ENABLE_AUTOLOCK = "enable_autolock"
