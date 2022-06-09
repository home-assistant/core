"""Support for MQTT message handling."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_DISCOVERY,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_CERTIFICATE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_COMMAND_TOPIC,
    CONF_DISCOVERY_PREFIX,
    CONF_ENCODING,
    CONF_KEEPALIVE,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_TLS_INSECURE,
    CONF_TLS_VERSION,
    CONF_WILL_MESSAGE,
    DEFAULT_BIRTH,
    DEFAULT_DISCOVERY,
    DEFAULT_ENCODING,
    DEFAULT_PREFIX,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
    DEFAULT_WILL,
    PLATFORMS,
    PROTOCOL_31,
    PROTOCOL_311,
)
from .util import _VALID_QOS_SCHEMA, valid_publish_topic, valid_subscribe_topic

DEFAULT_PORT = 1883
DEFAULT_KEEPALIVE = 60
DEFAULT_PROTOCOL = PROTOCOL_311
DEFAULT_TLS_PROTOCOL = "auto"

DEFAULT_VALUES = {
    CONF_BIRTH_MESSAGE: DEFAULT_BIRTH,
    CONF_DISCOVERY: DEFAULT_DISCOVERY,
    CONF_PORT: DEFAULT_PORT,
    CONF_TLS_VERSION: DEFAULT_TLS_PROTOCOL,
    CONF_WILL_MESSAGE: DEFAULT_WILL,
}

CLIENT_KEY_AUTH_MSG = (
    "client_key and client_cert must both be present in "
    "the MQTT broker configuration"
)

MQTT_WILL_BIRTH_SCHEMA = vol.Schema(
    {
        vol.Inclusive(ATTR_TOPIC, "topic_payload"): valid_publish_topic,
        vol.Inclusive(ATTR_PAYLOAD, "topic_payload"): cv.string,
        vol.Optional(ATTR_QOS, default=DEFAULT_QOS): _VALID_QOS_SCHEMA,
        vol.Optional(ATTR_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    },
    required=True,
)

PLATFORM_CONFIG_SCHEMA_BASE = vol.Schema(
    {vol.Optional(platform.value): cv.ensure_list for platform in PLATFORMS}
)

CONFIG_SCHEMA_BASE = PLATFORM_CONFIG_SCHEMA_BASE.extend(
    {
        vol.Optional(CONF_CLIENT_ID): cv.string,
        vol.Optional(CONF_KEEPALIVE, default=DEFAULT_KEEPALIVE): vol.All(
            vol.Coerce(int), vol.Range(min=15)
        ),
        vol.Optional(CONF_BROKER): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CERTIFICATE): vol.Any("auto", cv.isfile),
        vol.Inclusive(
            CONF_CLIENT_KEY, "client_key_auth", msg=CLIENT_KEY_AUTH_MSG
        ): cv.isfile,
        vol.Inclusive(
            CONF_CLIENT_CERT, "client_key_auth", msg=CLIENT_KEY_AUTH_MSG
        ): cv.isfile,
        vol.Optional(CONF_TLS_INSECURE): cv.boolean,
        vol.Optional(CONF_TLS_VERSION): vol.Any("auto", "1.0", "1.1", "1.2"),
        vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.All(
            cv.string, vol.In([PROTOCOL_31, PROTOCOL_311])
        ),
        vol.Optional(CONF_WILL_MESSAGE): MQTT_WILL_BIRTH_SCHEMA,
        vol.Optional(CONF_BIRTH_MESSAGE): MQTT_WILL_BIRTH_SCHEMA,
        vol.Optional(CONF_DISCOVERY): cv.boolean,
        # discovery_prefix must be a valid publish topic because if no
        # state topic is specified, it will be created with the given prefix.
        vol.Optional(
            CONF_DISCOVERY_PREFIX, default=DEFAULT_PREFIX
        ): valid_publish_topic,
    }
)

DEPRECATED_CONFIG_KEYS = [
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_DISCOVERY,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TLS_VERSION,
    CONF_USERNAME,
    CONF_WILL_MESSAGE,
]

SCHEMA_BASE = {
    vol.Optional(CONF_QOS, default=DEFAULT_QOS): _VALID_QOS_SCHEMA,
    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
}

MQTT_BASE_SCHEMA = vol.Schema(SCHEMA_BASE)

# Sensor type platforms subscribe to MQTT events
MQTT_RO_SCHEMA = MQTT_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)

# Switch type platforms publish to MQTT and may subscribe
MQTT_RW_SCHEMA = MQTT_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
    }
)
