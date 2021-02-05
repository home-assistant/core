"""Constants for the Epson integration."""
from epson_projector.const import CMODE_LIST_SET
import voluptuous as vol

from homeassistant.components.media_player import (
    DEVICE_CLASSES_SCHEMA as MEDIA_PLAYER_DEVICE_CLASSES_SCHEMA,
    DOMAIN as MEDIA_PLAYER_PLATFORM,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_NAMESPACE,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SCAN_INTERVAL,
)
import homeassistant.helpers.config_validation as cv

# Configuration names
CONF_PROJECTORS = "projectors"
CONF_SERVICE_SELECT_CMODE = "select_cmode"
CONF_CMODE = "cmode"

# Integration name
EPSON_DOMAIN = "epson"

# Default values
DEFAULT_NAME = "EPSON Projector"
DEFAULT_SCAN_INTERVAL = 10  # seconds
DEFAULT_PORT = 80

# Supported protocols
PROTO_HTTP = "http"
PROTO_TCP = "tcp"
PROTO_SERIAL = "serial"

# Supported platforms
PLATFORMS = [MEDIA_PLAYER_PLATFORM]

# Schemes
BASE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
    }
)

PROJECTORS_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PROTOCOL, default=PROTO_HTTP): vol.In(
            [PROTO_HTTP, PROTO_TCP, PROTO_SERIAL]
        ),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            cv.time_period, lambda value: value.total_seconds()
        ),
        vol.Optional(CONF_ENTITY_NAMESPACE): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): MEDIA_PLAYER_DEVICE_CLASSES_SCHEMA,
    }
)

PROJECTOR_CONFIG_FLOW_SCHEMA = BASE_SCHEMA.extend(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_PROTOCOL, default=PROTO_HTTP): vol.In(
            [PROTO_HTTP, PROTO_TCP, PROTO_SERIAL]
        ),
    }
)

SERVICE_SELECT_CMODE_SCHEMA = vol.Schema(
    {vol.Required(CONF_CMODE): vol.All(cv.string, vol.Any(*CMODE_LIST_SET))}
)

CONFIG_SCHEMA = vol.Schema(
    {
        EPSON_DOMAIN: {
            vol.Optional(CONF_PROJECTORS): vol.All(cv.ensure_list, [PROJECTORS_SCHEMA]),
        }
    },
    extra=vol.ALLOW_EXTRA,
)
