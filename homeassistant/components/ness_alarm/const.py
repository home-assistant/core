"""Constants for the Ness Alarm integration."""

from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import Platform

DOMAIN = "ness_alarm"

# Platforms
PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR]

# Configuration constants
CONF_DEVICE_PORT = "port"
CONF_INFER_ARMING_STATE = "infer_arming_state"
CONF_ZONES = "zones"
CONF_ZONE_NAME = "name"
CONF_ZONE_TYPE = "type"
CONF_ZONE_ID = "id"
CONF_ZONE_NUMBER = "zone_number"

# Subentry types
SUBENTRY_TYPE_ALARM = "alarm"
SUBENTRY_TYPE_ZONE = "zone"

# Defaults
DEFAULT_PORT = 4999
DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)
DEFAULT_INFER_ARMING_STATE = False
DEFAULT_ZONE_TYPE = BinarySensorDeviceClass.MOTION

# Options flow keys (deprecated - kept for backward compatibility during migration)
OPTIONS_ZONES = "zone_options"

# Signals
SIGNAL_ZONE_CHANGED = "ness_alarm.zone_changed"
SIGNAL_ARMING_STATE_CHANGED = "ness_alarm.arming_state_changed"

# Services
SERVICE_PANIC = "panic"
SERVICE_AUX = "aux"
ATTR_OUTPUT_ID = "output_id"
