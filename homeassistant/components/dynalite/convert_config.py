"""Convert the HA config to the dynalite config."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dynalite_devices_lib import const as dyn_const

from homeassistant.const import (
    CONF_DEFAULT,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_ROOM,
    CONF_TYPE,
)

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
    CONF_TIME_COVER,
)

ACTIVE_MAP = {
    ACTIVE_INIT: dyn_const.ACTIVE_INIT,
    False: dyn_const.ACTIVE_OFF,
    ACTIVE_OFF: dyn_const.ACTIVE_OFF,
    ACTIVE_ON: dyn_const.ACTIVE_ON,
    True: dyn_const.ACTIVE_ON,
}

TEMPLATE_MAP = {
    CONF_ROOM: dyn_const.CONF_ROOM,
    CONF_TIME_COVER: dyn_const.CONF_TIME_COVER,
}


def convert_with_map(config, conf_map):
    """Create the initial converted map with just the basic key:value pairs updated."""
    result = {}
    for conf in conf_map:
        if conf in config:
            result[conf_map[conf]] = config[conf]
    return result


def convert_channel(config: dict[str, Any]) -> dict[str, Any]:
    """Convert the config for a channel."""
    my_map = {
        CONF_NAME: dyn_const.CONF_NAME,
        CONF_FADE: dyn_const.CONF_FADE,
        CONF_TYPE: dyn_const.CONF_CHANNEL_TYPE,
    }
    return convert_with_map(config, my_map)


def convert_preset(config: dict[str, Any]) -> dict[str, Any]:
    """Convert the config for a preset."""
    my_map = {
        CONF_NAME: dyn_const.CONF_NAME,
        CONF_FADE: dyn_const.CONF_FADE,
        CONF_LEVEL: dyn_const.CONF_LEVEL,
    }
    return convert_with_map(config, my_map)


def convert_area(config: dict[str, Any]) -> dict[str, Any]:
    """Convert the config for an area."""
    my_map = {
        CONF_NAME: dyn_const.CONF_NAME,
        CONF_FADE: dyn_const.CONF_FADE,
        CONF_NO_DEFAULT: dyn_const.CONF_NO_DEFAULT,
        CONF_ROOM_ON: dyn_const.CONF_ROOM_ON,
        CONF_ROOM_OFF: dyn_const.CONF_ROOM_OFF,
        CONF_CHANNEL_COVER: dyn_const.CONF_CHANNEL_COVER,
        CONF_DEVICE_CLASS: dyn_const.CONF_DEVICE_CLASS,
        CONF_OPEN_PRESET: dyn_const.CONF_OPEN_PRESET,
        CONF_CLOSE_PRESET: dyn_const.CONF_CLOSE_PRESET,
        CONF_STOP_PRESET: dyn_const.CONF_STOP_PRESET,
        CONF_DURATION: dyn_const.CONF_DURATION,
        CONF_TILT_TIME: dyn_const.CONF_TILT_TIME,
    }
    result = convert_with_map(config, my_map)
    if CONF_CHANNEL in config:
        result[dyn_const.CONF_CHANNEL] = {
            channel: convert_channel(channel_conf)
            for (channel, channel_conf) in config[CONF_CHANNEL].items()
        }
    if CONF_PRESET in config:
        result[dyn_const.CONF_PRESET] = {
            preset: convert_preset(preset_conf)
            for (preset, preset_conf) in config[CONF_PRESET].items()
        }
    if CONF_TEMPLATE in config:
        result[dyn_const.CONF_TEMPLATE] = TEMPLATE_MAP[config[CONF_TEMPLATE]]
    return result


def convert_default(config: dict[str, Any]) -> dict[str, Any]:
    """Convert the config for the platform defaults."""
    return convert_with_map(config, {CONF_FADE: dyn_const.CONF_FADE})


def convert_template(config: dict[str, Any]) -> dict[str, Any]:
    """Convert the config for a template."""
    my_map = {
        CONF_ROOM_ON: dyn_const.CONF_ROOM_ON,
        CONF_ROOM_OFF: dyn_const.CONF_ROOM_OFF,
        CONF_CHANNEL_COVER: dyn_const.CONF_CHANNEL_COVER,
        CONF_DEVICE_CLASS: dyn_const.CONF_DEVICE_CLASS,
        CONF_OPEN_PRESET: dyn_const.CONF_OPEN_PRESET,
        CONF_CLOSE_PRESET: dyn_const.CONF_CLOSE_PRESET,
        CONF_STOP_PRESET: dyn_const.CONF_STOP_PRESET,
        CONF_DURATION: dyn_const.CONF_DURATION,
        CONF_TILT_TIME: dyn_const.CONF_TILT_TIME,
    }
    return convert_with_map(config, my_map)


def convert_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a config dict by replacing component consts with library consts."""
    my_map = {
        CONF_NAME: dyn_const.CONF_NAME,
        CONF_HOST: dyn_const.CONF_HOST,
        CONF_PORT: dyn_const.CONF_PORT,
        CONF_AUTO_DISCOVER: dyn_const.CONF_AUTO_DISCOVER,
        CONF_POLL_TIMER: dyn_const.CONF_POLL_TIMER,
    }
    result = convert_with_map(config, my_map)
    if CONF_AREA in config:
        result[dyn_const.CONF_AREA] = {
            area: convert_area(area_conf)
            for (area, area_conf) in config[CONF_AREA].items()
        }
    if CONF_DEFAULT in config:
        result[dyn_const.CONF_DEFAULT] = convert_default(config[CONF_DEFAULT])
    if CONF_ACTIVE in config:
        result[dyn_const.CONF_ACTIVE] = ACTIVE_MAP[config[CONF_ACTIVE]]
    if CONF_PRESET in config:
        result[dyn_const.CONF_PRESET] = {
            preset: convert_preset(preset_conf)
            for (preset, preset_conf) in config[CONF_PRESET].items()
        }
    if CONF_TEMPLATE in config:
        result[dyn_const.CONF_TEMPLATE] = {
            TEMPLATE_MAP[template]: convert_template(template_conf)
            for (template, template_conf) in config[CONF_TEMPLATE].items()
        }
    return result
