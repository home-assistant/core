"""Shared schemas for MQTT discovery and YAML config items."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    CONF_DEVICE,
    CONF_ENTITY_CATEGORY,
    CONF_ICON,
    CONF_MODEL,
    CONF_MODEL_ID,
    CONF_NAME,
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
    CONF_CONFIGURATION_URL,
    CONF_CONNECTIONS,
    CONF_DEPRECATED_VIA_HUB,
    CONF_ENABLED_BY_DEFAULT,
    CONF_HW_VERSION,
    CONF_IDENTIFIERS,
    CONF_JSON_ATTRS_TEMPLATE,
    CONF_JSON_ATTRS_TOPIC,
    CONF_MANUFACTURER,
    CONF_OBJECT_ID,
    CONF_ORIGIN,
    CONF_PAYLOAD_AVAILABLE,
    CONF_PAYLOAD_NOT_AVAILABLE,
    CONF_SERIAL_NUMBER,
    CONF_SUGGESTED_AREA,
    CONF_SUPPORT_URL,
    CONF_SW_VERSION,
    CONF_TOPIC,
    CONF_VIA_DEVICE,
    DEFAULT_PAYLOAD_AVAILABLE,
    DEFAULT_PAYLOAD_NOT_AVAILABLE,
)
from .util import valid_subscribe_topic

MQTT_AVAILABILITY_SINGLE_SCHEMA = vol.Schema(
    {
        vol.Exclusive(CONF_AVAILABILITY_TOPIC, "availability"): valid_subscribe_topic,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(
            CONF_PAYLOAD_AVAILABLE, default=DEFAULT_PAYLOAD_AVAILABLE
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_NOT_AVAILABLE, default=DEFAULT_PAYLOAD_NOT_AVAILABLE
        ): cv.string,
    }
)

MQTT_AVAILABILITY_LIST_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AVAILABILITY_MODE, default=AVAILABILITY_LATEST): vol.All(
            cv.string, vol.In(AVAILABILITY_MODES)
        ),
        vol.Exclusive(CONF_AVAILABILITY, "availability"): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_TOPIC): valid_subscribe_topic,
                    vol.Optional(
                        CONF_PAYLOAD_AVAILABLE, default=DEFAULT_PAYLOAD_AVAILABLE
                    ): cv.string,
                    vol.Optional(
                        CONF_PAYLOAD_NOT_AVAILABLE,
                        default=DEFAULT_PAYLOAD_NOT_AVAILABLE,
                    ): cv.string,
                    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
                }
            ],
        ),
    }
)

MQTT_AVAILABILITY_SCHEMA = MQTT_AVAILABILITY_SINGLE_SCHEMA.extend(
    MQTT_AVAILABILITY_LIST_SCHEMA.schema
)


def validate_device_has_at_least_one_identifier(value: ConfigType) -> ConfigType:
    """Validate that a device info entry has at least one identifying value."""
    if value.get(CONF_IDENTIFIERS) or value.get(CONF_CONNECTIONS):
        return value
    raise vol.Invalid(
        "Device must have at least one identifying value in "
        "'identifiers' and/or 'connections'"
    )


MQTT_ENTITY_DEVICE_INFO_SCHEMA = vol.All(
    cv.deprecated(CONF_DEPRECATED_VIA_HUB, CONF_VIA_DEVICE),
    vol.Schema(
        {
            vol.Optional(CONF_IDENTIFIERS, default=list): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_CONNECTIONS, default=list): vol.All(
                cv.ensure_list, [vol.All(vol.Length(2), [cv.string])]
            ),
            vol.Optional(CONF_MANUFACTURER): cv.string,
            vol.Optional(CONF_MODEL): cv.string,
            vol.Optional(CONF_MODEL_ID): cv.string,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_HW_VERSION): cv.string,
            vol.Optional(CONF_SERIAL_NUMBER): cv.string,
            vol.Optional(CONF_SW_VERSION): cv.string,
            vol.Optional(CONF_VIA_DEVICE): cv.string,
            vol.Optional(CONF_SUGGESTED_AREA): cv.string,
            vol.Optional(CONF_CONFIGURATION_URL): cv.configuration_url,
        }
    ),
    validate_device_has_at_least_one_identifier,
)


MQTT_ORIGIN_INFO_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_SW_VERSION): cv.string,
            vol.Optional(CONF_SUPPORT_URL): cv.configuration_url,
        }
    ),
)

MQTT_ENTITY_COMMON_SCHEMA = MQTT_AVAILABILITY_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Optional(CONF_ORIGIN): MQTT_ORIGIN_INFO_SCHEMA,
        vol.Optional(CONF_ENABLED_BY_DEFAULT, default=True): cv.boolean,
        vol.Optional(CONF_ENTITY_CATEGORY): ENTITY_CATEGORIES_SCHEMA,
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(CONF_JSON_ATTRS_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_JSON_ATTRS_TEMPLATE): cv.template,
        vol.Optional(CONF_OBJECT_ID): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)
