"""Schema for config entries."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.cover import DEVICE_CLASSES_SCHEMA
from homeassistant.const import CONF_DEFAULT, CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.helpers import config_validation as cv

from .const import (
    ACTIVE_INIT,
    ACTIVE_OFF,
    ACTIVE_ON,
    CONF_ACTIVE,
    CONF_AREA,
    CONF_AUTO_DISCOVER,
    CONF_CHANNEL,
    CONF_CHANNEL_COVER,
    CONF_CLOSE_PRESET,
    CONF_DEVICE_CLASS,
    CONF_DURATION,
    CONF_FADE,
    CONF_LEVEL,
    CONF_NO_DEFAULT,
    CONF_OPEN_PRESET,
    CONF_POLL_TIMER,
    CONF_PRESET,
    CONF_ROOM_OFF,
    CONF_ROOM_ON,
    CONF_STOP_PRESET,
    CONF_TEMPLATE,
    CONF_TILT_TIME,
    DEFAULT_CHANNEL_TYPE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TEMPLATES,
)


def num_string(value: str | int) -> str:
    """Test if value is a string of digits, aka an integer."""
    new_value = str(value)
    if new_value.isdigit():
        return new_value
    raise vol.Invalid("Not a string with numbers")


CHANNEL_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_FADE): vol.Coerce(float),
        vol.Optional(CONF_TYPE, default=DEFAULT_CHANNEL_TYPE): vol.Any(
            "light", "switch"
        ),
    }
)

CHANNEL_SCHEMA = vol.Schema({num_string: CHANNEL_DATA_SCHEMA})

PRESET_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_FADE): vol.Coerce(float),
        vol.Optional(CONF_LEVEL): vol.Coerce(float),
    }
)

PRESET_SCHEMA = vol.Schema({num_string: vol.Any(PRESET_DATA_SCHEMA, None)})

TEMPLATE_ROOM_SCHEMA = vol.Schema(
    {vol.Optional(CONF_ROOM_ON): num_string, vol.Optional(CONF_ROOM_OFF): num_string}
)

TEMPLATE_TIMECOVER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_CHANNEL_COVER): num_string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_OPEN_PRESET): num_string,
        vol.Optional(CONF_CLOSE_PRESET): num_string,
        vol.Optional(CONF_STOP_PRESET): num_string,
        vol.Optional(CONF_DURATION): vol.Coerce(float),
        vol.Optional(CONF_TILT_TIME): vol.Coerce(float),
    }
)

TEMPLATE_DATA_SCHEMA = vol.Any(TEMPLATE_ROOM_SCHEMA, TEMPLATE_TIMECOVER_SCHEMA)

TEMPLATE_SCHEMA = vol.Schema({str: TEMPLATE_DATA_SCHEMA})


def validate_area(config: dict[str, Any]) -> dict[str, Any]:
    """Validate that template parameters are only used if area is using the relevant template."""
    conf_set = set()
    for configs in DEFAULT_TEMPLATES.values():
        for conf in configs:
            conf_set.add(conf)
    if config.get(CONF_TEMPLATE):
        for conf in DEFAULT_TEMPLATES[config[CONF_TEMPLATE]]:
            conf_set.remove(conf)
    for conf in conf_set:
        if config.get(conf):
            raise vol.Invalid(
                f"{conf} should not be part of area {config[CONF_NAME]} config"
            )
    return config


AREA_DATA_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_TEMPLATE): vol.In(DEFAULT_TEMPLATES),
            vol.Optional(CONF_FADE): vol.Coerce(float),
            vol.Optional(CONF_NO_DEFAULT): cv.boolean,
            vol.Optional(CONF_CHANNEL): CHANNEL_SCHEMA,
            vol.Optional(CONF_PRESET): PRESET_SCHEMA,
            # the next ones can be part of the templates
            vol.Optional(CONF_ROOM_ON): num_string,
            vol.Optional(CONF_ROOM_OFF): num_string,
            vol.Optional(CONF_CHANNEL_COVER): num_string,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_OPEN_PRESET): num_string,
            vol.Optional(CONF_CLOSE_PRESET): num_string,
            vol.Optional(CONF_STOP_PRESET): num_string,
            vol.Optional(CONF_DURATION): vol.Coerce(float),
            vol.Optional(CONF_TILT_TIME): vol.Coerce(float),
        },
        validate_area,
    )
)

AREA_SCHEMA = vol.Schema({num_string: vol.Any(AREA_DATA_SCHEMA, None)})

PLATFORM_DEFAULTS_SCHEMA = vol.Schema({vol.Optional(CONF_FADE): vol.Coerce(float)})


BRIDGE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_AUTO_DISCOVER, default=False): vol.Coerce(bool),
        vol.Optional(CONF_POLL_TIMER, default=1.0): vol.Coerce(float),
        vol.Optional(CONF_AREA): AREA_SCHEMA,
        vol.Optional(CONF_DEFAULT): PLATFORM_DEFAULTS_SCHEMA,
        vol.Optional(CONF_ACTIVE, default=False): vol.Any(
            ACTIVE_ON, ACTIVE_OFF, ACTIVE_INIT, cv.boolean
        ),
        vol.Optional(CONF_PRESET): PRESET_SCHEMA,
        vol.Optional(CONF_TEMPLATE): TEMPLATE_SCHEMA,
    }
)
