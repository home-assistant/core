"""Support for MQTT message handling."""

import probatio

from homeassistant.const import CONF_OPTIMISTIC, CONF_VALUE_TEMPLATE
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_GROUP,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    DEFAULT_ENCODING,
    DEFAULT_OPTIMISTIC,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
)
from .util import valid_publish_topic, valid_qos_schema, valid_subscribe_topic

SCHEMA_BASE = {
    probatio.Optional(CONF_QOS, default=DEFAULT_QOS): valid_qos_schema,
    probatio.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
    probatio.Optional(CONF_GROUP): probatio.All(cv.ensure_list, [cv.string]),
}

MQTT_BASE_SCHEMA = probatio.Schema(SCHEMA_BASE)

# Sensor type platforms subscribe to MQTT events
MQTT_RO_SCHEMA = MQTT_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)

# Switch type platforms publish to MQTT and may subscribe
MQTT_RW_SCHEMA = MQTT_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        probatio.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        probatio.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
    }
)
