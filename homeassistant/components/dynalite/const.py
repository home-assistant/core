"""Constants for the Dynalite component."""
import logging

LOGGER = logging.getLogger(__package__)
DOMAIN = "dynalite"

ENTITY_PLATFORMS = ["light", "switch"]


CONF_ACTIVE = "active"
CONF_ACTIVE_INIT = "init"
CONF_ACTIVE_OFF = "off"
CONF_ACTIVE_ON = "on"
CONF_ALL = "ALL"
CONF_AREA = "area"
CONF_AUTO_DISCOVER = "autodiscover"
CONF_BRIDGES = "bridges"
CONF_CHANNEL = "channel"
CONF_CHANNEL_TYPE = "type"
CONF_DEFAULT = "default"
CONF_FADE = "fade"
CONF_HOST = "host"
CONF_NAME = "name"
CONF_NO_DEFAULT = "nodefault"
CONF_POLLTIMER = "polltimer"
CONF_PORT = "port"
CONF_PRESET = "preset"

DEFAULT_CHANNEL_TYPE = "light"
DEFAULT_NAME = "dynalite"
DEFAULT_PORT = 12345
