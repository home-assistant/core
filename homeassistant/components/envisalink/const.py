"""Constants for the Envisalink integration."""

from homeassistant.const import Platform

DOMAIN = "envisalink"

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_EVL_PORT = "port"
CONF_EVL_VERSION = "evl_version"
CONF_PANEL_TYPE = "panel_type"
CONF_PANIC = "panic_type"
CONF_PARTITIONNAME = "name"
CONF_PARTITIONS = "partitions"
CONF_PARTITION_NUMBER = "partition_number"
CONF_PASS = "password"
CONF_USERNAME = "user_name"
CONF_ZONENAME = "name"
CONF_ZONES = "zones"
CONF_ZONETYPE = "type"
CONF_ZONE_NUMBER = "zone_number"

PANEL_TYPE_HONEYWELL = "HONEYWELL"
PANEL_TYPE_DSC = "DSC"

EVL_VERSIONS = [3, 4]

# Matches pyenvisalink's own EnvisalinkAlarmPanel limits: 64 zones below EVL
# version 4, 128 from version 4 on; partitions are always capped at 8.
MAX_ZONES_BY_EVL_VERSION = {3: 64, 4: 128}
MAX_PARTITIONS = 8

PANIC_TYPES = ["Fire", "Ambulance", "Police"]

DEFAULT_PORT = 4025
DEFAULT_EVL_VERSION = 3
DEFAULT_KEEPALIVE = 60
DEFAULT_ZONEDUMP_INTERVAL = 30
DEFAULT_ZONETYPE = "opening"
DEFAULT_PANIC = "Police"
DEFAULT_TIMEOUT = 10

# Extra time allowed, on top of the connection timeout, for the panel to
# respond to the login handshake once the raw TCP connection succeeds.
LOGIN_RESPONSE_TIMEOUT = 10

SIGNAL_ZONE_UPDATE = "envisalink.zones_updated"
SIGNAL_PARTITION_UPDATE = "envisalink.partition_updated"
SIGNAL_KEYPAD_UPDATE = "envisalink.keypad_updated"
SIGNAL_ZONE_BYPASS_UPDATE = "envisalink.zone_bypass_updated"

SUBENTRY_TYPE_ZONE = "zone"
SUBENTRY_TYPE_PARTITION = "partition"

SERVICE_CUSTOM_FUNCTION = "invoke_custom_function"
ATTR_CUSTOM_FUNCTION = "pgm"
ATTR_PARTITION = "partition"

SERVICE_ALARM_KEYPRESS = "alarm_keypress"
ATTR_KEYPRESS = "keypress"
