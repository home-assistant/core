"""Constants for the Envisalink integration."""

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import EnvisalinkData

DOMAIN = "envisalink"

DATA_EVL: HassKey[EnvisalinkData] = HassKey(DOMAIN)

CONF_EVL_KEEPALIVE = "keepalive_interval"
CONF_EVL_PORT = "port"
CONF_EVL_VERSION = "evl_version"
CONF_PANEL_TYPE = "panel_type"
CONF_PANIC = "panic_type"
CONF_PARTITIONNAME = "name"
CONF_PARTITIONS = "partitions"
CONF_PASS = "password"
CONF_USERNAME = "user_name"
CONF_ZONEDUMP_INTERVAL = "zonedump_interval"
CONF_ZONENAME = "name"
CONF_ZONES = "zones"
CONF_ZONETYPE = "type"

PANEL_TYPE_HONEYWELL = "HONEYWELL"
PANEL_TYPE_DSC = "DSC"

DEFAULT_PORT = 4025
DEFAULT_EVL_VERSION = 3
DEFAULT_KEEPALIVE = 60
DEFAULT_ZONEDUMP_INTERVAL = 30
DEFAULT_ZONETYPE = "opening"
DEFAULT_PANIC = "Police"
DEFAULT_TIMEOUT = 10

SIGNAL_ZONE_UPDATE = "envisalink.zones_updated"
SIGNAL_PARTITION_UPDATE = "envisalink.partition_updated"
SIGNAL_KEYPAD_UPDATE = "envisalink.keypad_updated"
SIGNAL_ZONE_BYPASS_UPDATE = "envisalink.zone_bypass_updated"

SERVICE_CUSTOM_FUNCTION = "invoke_custom_function"
ATTR_CUSTOM_FUNCTION = "pgm"
ATTR_PARTITION = "partition"
