"""Shared schemas for MQTT discovery and YAML config items."""

from typing import Any

import probatio

from homeassistant.const import (
    CONF_DEVICE,
    CONF_ENTITY_CATEGORY,
    CONF_ICON,
    CONF_MODEL,
    CONF_MODEL_ID,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ENTITY_CATEGORIES_SCHEMA
from homeassistant.helpers.typing import ConfigType

from .const import (
    AVAILABILITY_LATEST,
    AVAILABILITY_MODES,
    CONF_AVAILABILITY,
    CONF_AVAILABILITY_MODE,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_AVAILABILITY_TOPIC,
    CONF_COMMAND_TOPIC,
    CONF_COMPONENTS,
    CONF_CONFIGURATION_URL,
    CONF_CONNECTIONS,
    CONF_DEFAULT_ENTITY_ID,
    CONF_DEPRECATED_VIA_HUB,
    CONF_ENABLED_BY_DEFAULT,
    CONF_ENCODING,
    CONF_ENTITY_PICTURE,
    CONF_HW_VERSION,
    CONF_IDENTIFIERS,
    CONF_JSON_ATTRS_TEMPLATE,
    CONF_JSON_ATTRS_TOPIC,
    CONF_MANUFACTURER,
    CONF_MESSAGE_EXPIRY_INTERVAL,
    CONF_ORIGIN,
    CONF_PAYLOAD_AVAILABLE,
    CONF_PAYLOAD_NOT_AVAILABLE,
    CONF_QOS,
    CONF_SERIAL_NUMBER,
    CONF_STATE_TOPIC,
    CONF_SUGGESTED_AREA,
    CONF_SUPPORT_URL,
    CONF_SW_VERSION,
    CONF_TOPIC,
    CONF_VIA_DEVICE,
    CONF_VISIBLE_BY_DEFAULT,
    DEFAULT_PAYLOAD_AVAILABLE,
    DEFAULT_PAYLOAD_NOT_AVAILABLE,
    ENTITY_PLATFORMS,
    SUPPORTED_COMPONENTS,
)
from .util import valid_publish_topic, valid_qos_schema, valid_subscribe_topic

# Device discovery options that are also available at entity component level
SHARED_OPTIONS = [
    CONF_AVAILABILITY,
    CONF_AVAILABILITY_MODE,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_AVAILABILITY_TOPIC,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_MESSAGE_EXPIRY_INTERVAL,
    CONF_PAYLOAD_AVAILABLE,
    CONF_PAYLOAD_NOT_AVAILABLE,
    CONF_STATE_TOPIC,
    CONF_QOS,
]


_MQTT_AVAILABILITY_SINGLE_SCHEMA = probatio.Schema(
    {
        probatio.Exclusive(
            CONF_AVAILABILITY_TOPIC, "availability"
        ): valid_subscribe_topic,
        probatio.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        probatio.Optional(
            CONF_PAYLOAD_AVAILABLE, default=DEFAULT_PAYLOAD_AVAILABLE
        ): cv.string,
        probatio.Optional(
            CONF_PAYLOAD_NOT_AVAILABLE, default=DEFAULT_PAYLOAD_NOT_AVAILABLE
        ): cv.string,
    }
)

_MQTT_AVAILABILITY_LIST_SCHEMA = probatio.Schema(
    {
        probatio.Optional(
            CONF_AVAILABILITY_MODE, default=AVAILABILITY_LATEST
        ): probatio.All(cv.string, probatio.In(AVAILABILITY_MODES)),
        probatio.Exclusive(CONF_AVAILABILITY, "availability"): probatio.All(
            cv.ensure_list,
            [
                {
                    probatio.Required(CONF_TOPIC): valid_subscribe_topic,
                    probatio.Optional(
                        CONF_PAYLOAD_AVAILABLE, default=DEFAULT_PAYLOAD_AVAILABLE
                    ): cv.string,
                    probatio.Optional(
                        CONF_PAYLOAD_NOT_AVAILABLE,
                        default=DEFAULT_PAYLOAD_NOT_AVAILABLE,
                    ): cv.string,
                    probatio.Optional(CONF_VALUE_TEMPLATE): cv.template,
                }
            ],
        ),
    }
)

_MQTT_AVAILABILITY_SCHEMA = _MQTT_AVAILABILITY_SINGLE_SCHEMA.extend(
    _MQTT_AVAILABILITY_LIST_SCHEMA.schema
)


def validate_device_has_at_least_one_identifier(value: ConfigType) -> ConfigType:
    """Validate that a device info entry has at least one identifying value."""
    if value.get(CONF_IDENTIFIERS) or value.get(CONF_CONNECTIONS):
        return value
    raise probatio.Invalid(
        "Device must have at least one identifying value in "
        "'identifiers' and/or 'connections'"
    )


MQTT_ENTITY_DEVICE_INFO_SCHEMA = probatio.All(
    cv.deprecated(CONF_DEPRECATED_VIA_HUB, CONF_VIA_DEVICE),
    probatio.Schema(
        {
            probatio.Optional(CONF_IDENTIFIERS, default=list): probatio.All(
                cv.ensure_list, [cv.string]
            ),
            probatio.Optional(CONF_CONNECTIONS, default=list): probatio.All(
                cv.ensure_list, [probatio.All(probatio.Length(2), [cv.string])]
            ),
            probatio.Optional(CONF_MANUFACTURER): cv.string,
            probatio.Optional(CONF_MODEL): cv.string,
            probatio.Optional(CONF_MODEL_ID): cv.string,
            probatio.Optional(CONF_NAME): cv.string,
            probatio.Optional(CONF_HW_VERSION): cv.string,
            probatio.Optional(CONF_SERIAL_NUMBER): cv.string,
            probatio.Optional(CONF_SW_VERSION): cv.string,
            probatio.Optional(CONF_VIA_DEVICE): cv.string,
            probatio.Optional(CONF_SUGGESTED_AREA): cv.string,
            probatio.Optional(CONF_CONFIGURATION_URL): cv.configuration_url,
        }
    ),
    validate_device_has_at_least_one_identifier,
)


MQTT_ORIGIN_INFO_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Required(CONF_NAME): cv.string,
            probatio.Optional(CONF_SW_VERSION): cv.string,
            probatio.Optional(CONF_SUPPORT_URL): cv.configuration_url,
        }
    ),
)


def valid_message_expiry_interval(value: Any) -> int:
    """Return Message Expiry Interval in seconds."""
    if isinstance(value, int):
        return cv.positive_int(value)  # type: ignore[no-any-return]
    return int(cv.positive_time_period_dict(value).total_seconds())


MQTT_ENTITY_COMMON_SCHEMA = _MQTT_AVAILABILITY_SCHEMA.extend(
    {
        probatio.Optional(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        probatio.Optional(CONF_ENTITY_PICTURE): cv.url,
        probatio.Optional(CONF_ORIGIN): MQTT_ORIGIN_INFO_SCHEMA,
        probatio.Optional(CONF_ENABLED_BY_DEFAULT, default=True): cv.boolean,
        probatio.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        probatio.Optional(CONF_ICON): cv.icon,
        probatio.Optional(CONF_JSON_ATTRS_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_JSON_ATTRS_TEMPLATE): cv.template,
        probatio.Optional(CONF_DEFAULT_ENTITY_ID): cv.string,
        probatio.Optional(CONF_MESSAGE_EXPIRY_INTERVAL): valid_message_expiry_interval,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
        probatio.Optional(CONF_VISIBLE_BY_DEFAULT, default=True): cv.boolean,
    }
)

_UNIQUE_ID_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_UNIQUE_ID): cv.string},
).extend({}, extra=True)


def check_unique_id(config: dict[str, Any]) -> dict[str, Any]:
    """Check if a unique ID is set in case an entity platform is configured."""
    platform = config[CONF_PLATFORM]
    if platform in ENTITY_PLATFORMS and len(config.keys()) > 1:
        _UNIQUE_ID_SCHEMA(config)
    return config


_COMPONENT_CONFIG_SCHEMA = probatio.All(
    probatio.Schema(
        {probatio.Required(CONF_PLATFORM): probatio.In(SUPPORTED_COMPONENTS)},
    ).extend({}, extra=True),
    check_unique_id,
)

DEVICE_DISCOVERY_SCHEMA = _MQTT_AVAILABILITY_SCHEMA.extend(
    {
        probatio.Required(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        probatio.Required(CONF_COMPONENTS): probatio.Schema(
            {str: _COMPONENT_CONFIG_SCHEMA}
        ),
        probatio.Required(CONF_ORIGIN): MQTT_ORIGIN_INFO_SCHEMA,
        probatio.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
        probatio.Optional(CONF_COMMAND_TOPIC): valid_publish_topic,
        probatio.Optional(CONF_MESSAGE_EXPIRY_INTERVAL): valid_message_expiry_interval,
        probatio.Optional(CONF_QOS): valid_qos_schema,
        probatio.Optional(CONF_ENCODING): cv.string,
    }
)
