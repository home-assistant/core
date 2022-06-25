"""Utility functions for the MQTT integration."""
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_PAYLOAD
from homeassistant.helpers import config_validation as cv, template

from .const import (
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
)


def valid_topic(value: Any) -> str:
    """Validate that this is a valid topic name/filter."""
    value = cv.string(value)
    try:
        raw_value = value.encode("utf-8")
    except UnicodeError as err:
        raise vol.Invalid("MQTT topic name/filter must be valid UTF-8 string.") from err
    if not raw_value:
        raise vol.Invalid("MQTT topic name/filter must not be empty.")
    if len(raw_value) > 65535:
        raise vol.Invalid(
            "MQTT topic name/filter must not be longer than 65535 encoded bytes."
        )
    if "\0" in value:
        raise vol.Invalid("MQTT topic name/filter must not contain null character.")
    if any(char <= "\u001F" for char in value):
        raise vol.Invalid("MQTT topic name/filter must not contain control characters.")
    if any("\u007f" <= char <= "\u009F" for char in value):
        raise vol.Invalid("MQTT topic name/filter must not contain control characters.")
    if any("\ufdd0" <= char <= "\ufdef" for char in value):
        raise vol.Invalid("MQTT topic name/filter must not contain non-characters.")
    if any((ord(char) & 0xFFFF) in (0xFFFE, 0xFFFF) for char in value):
        raise vol.Invalid("MQTT topic name/filter must not contain noncharacters.")

    return value


def valid_subscribe_topic(value: Any) -> str:
    """Validate that we can subscribe using this MQTT topic."""
    value = valid_topic(value)
    for i in (i for i, c in enumerate(value) if c == "+"):
        if (i > 0 and value[i - 1] != "/") or (
            i < len(value) - 1 and value[i + 1] != "/"
        ):
            raise vol.Invalid(
                "Single-level wildcard must occupy an entire level of the filter"
            )

    index = value.find("#")
    if index != -1:
        if index != len(value) - 1:
            # If there are multiple wildcards, this will also trigger
            raise vol.Invalid(
                "Multi-level wildcard must be the last "
                "character in the topic filter."
            )
        if len(value) > 1 and value[index - 1] != "/":
            raise vol.Invalid(
                "Multi-level wildcard must be after a topic level separator."
            )

    return value


def valid_subscribe_topic_template(value: Any) -> template.Template:
    """Validate either a jinja2 template or a valid MQTT subscription topic."""
    tpl = template.Template(value)

    if tpl.is_static:
        valid_subscribe_topic(value)

    return tpl


def valid_publish_topic(value: Any) -> str:
    """Validate that we can publish using this MQTT topic."""
    value = valid_topic(value)
    if "+" in value or "#" in value:
        raise vol.Invalid("Wildcards can not be used in topic names")
    return value


_VALID_QOS_SCHEMA = vol.All(vol.Coerce(int), vol.In([0, 1, 2]))

MQTT_WILL_BIRTH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TOPIC): valid_publish_topic,
        vol.Required(ATTR_PAYLOAD, CONF_PAYLOAD): cv.string,
        vol.Optional(ATTR_QOS, default=DEFAULT_QOS): _VALID_QOS_SCHEMA,
        vol.Optional(ATTR_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    },
    required=True,
)
