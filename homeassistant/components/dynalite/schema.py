"""Schema for config entries."""

from typing import Any

import probatio

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
    raise probatio.Invalid("Not a string with numbers")


CHANNEL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME): cv.string,
        probatio.Optional(CONF_FADE): probatio.Coerce(float),
        probatio.Optional(CONF_TYPE, default=DEFAULT_CHANNEL_TYPE): probatio.Any(
            "light", "switch"
        ),
    }
)

CHANNEL_SCHEMA = probatio.Schema({num_string: CHANNEL_DATA_SCHEMA})

PRESET_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME): cv.string,
        probatio.Optional(CONF_FADE): probatio.Coerce(float),
        probatio.Optional(CONF_LEVEL): probatio.Coerce(float),
    }
)

PRESET_SCHEMA = probatio.Schema({num_string: probatio.Any(PRESET_DATA_SCHEMA, None)})

TEMPLATE_ROOM_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_ROOM_ON): num_string,
        probatio.Optional(CONF_ROOM_OFF): num_string,
    }
)

TEMPLATE_TIMECOVER_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_CHANNEL_COVER): num_string,
        probatio.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        probatio.Optional(CONF_OPEN_PRESET): num_string,
        probatio.Optional(CONF_CLOSE_PRESET): num_string,
        probatio.Optional(CONF_STOP_PRESET): num_string,
        probatio.Optional(CONF_DURATION): probatio.Coerce(float),
        probatio.Optional(CONF_TILT_TIME): probatio.Coerce(float),
    }
)

TEMPLATE_DATA_SCHEMA = probatio.Any(TEMPLATE_ROOM_SCHEMA, TEMPLATE_TIMECOVER_SCHEMA)

TEMPLATE_SCHEMA = probatio.Schema({str: TEMPLATE_DATA_SCHEMA})


def validate_area(config: dict[str, Any]) -> dict[str, Any]:
    """Validate template params are only used with relevant template."""
    conf_set = set()
    for configs in DEFAULT_TEMPLATES.values():
        for conf in configs:
            conf_set.add(conf)
    if config.get(CONF_TEMPLATE):
        for conf in DEFAULT_TEMPLATES[config[CONF_TEMPLATE]]:
            conf_set.remove(conf)
    for conf in conf_set:
        if config.get(conf):
            raise probatio.Invalid(
                f"{conf} should not be part of area {config[CONF_NAME]} config"
            )
    return config


AREA_DATA_SCHEMA = probatio.Schema(
    probatio.All(
        {
            probatio.Required(CONF_NAME): cv.string,
            probatio.Optional(CONF_TEMPLATE): probatio.In(DEFAULT_TEMPLATES),
            probatio.Optional(CONF_FADE): probatio.Coerce(float),
            probatio.Optional(CONF_NO_DEFAULT): cv.boolean,
            probatio.Optional(CONF_CHANNEL): CHANNEL_SCHEMA,
            probatio.Optional(CONF_PRESET): PRESET_SCHEMA,
            # the next ones can be part of the templates
            probatio.Optional(CONF_ROOM_ON): num_string,
            probatio.Optional(CONF_ROOM_OFF): num_string,
            probatio.Optional(CONF_CHANNEL_COVER): num_string,
            probatio.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            probatio.Optional(CONF_OPEN_PRESET): num_string,
            probatio.Optional(CONF_CLOSE_PRESET): num_string,
            probatio.Optional(CONF_STOP_PRESET): num_string,
            probatio.Optional(CONF_DURATION): probatio.Coerce(float),
            probatio.Optional(CONF_TILT_TIME): probatio.Coerce(float),
        },
        validate_area,
    )
)

AREA_SCHEMA = probatio.Schema({num_string: probatio.Any(AREA_DATA_SCHEMA, None)})

PLATFORM_DEFAULTS_SCHEMA = probatio.Schema(
    {probatio.Optional(CONF_FADE): probatio.Coerce(float)}
)


BRIDGE_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        probatio.Optional(CONF_AUTO_DISCOVER, default=False): probatio.Coerce(bool),
        probatio.Optional(CONF_POLL_TIMER, default=1.0): probatio.Coerce(float),
        probatio.Optional(CONF_AREA): AREA_SCHEMA,
        probatio.Optional(CONF_DEFAULT): PLATFORM_DEFAULTS_SCHEMA,
        probatio.Optional(CONF_ACTIVE, default=False): probatio.Any(
            ACTIVE_ON, ACTIVE_OFF, ACTIVE_INIT, cv.boolean
        ),
        probatio.Optional(CONF_PRESET): PRESET_SCHEMA,
        probatio.Optional(CONF_TEMPLATE): TEMPLATE_SCHEMA,
    }
)
