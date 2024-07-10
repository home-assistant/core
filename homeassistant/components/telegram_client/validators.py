"""Helper functions."""

from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    FIELD_FILE,
    FIELD_INLINE_KEYBOARD,
    FIELD_KEYBOARD,
    FIELD_KEYBOARD_RESIZE,
    FIELD_KEYBOARD_SINGLE_USE,
    FIELD_MESSAGE,
    FIELD_NOSOUND_VIDEO,
    FIELD_TARGET_ID,
    FIELD_TARGET_USERNAME,
)


def has_message_if_file_not_defined(conf: dict[str, Any]) -> dict[str, Any]:
    """Validate config has title if file is not specified."""
    if FIELD_MESSAGE not in conf and FIELD_FILE not in conf:
        raise vol.Invalid("You should specify message if file is not specified")
    return conf


def string_number(value: str) -> int:
    """Verify string number."""
    try:
        return int(value)
    except ValueError as err:
        raise vol.Invalid(f"{value} is not a valid integer string") from err


def comma_separated_targets(value: str) -> str:
    """Verify string is a comma separated targets."""
    targets = cv.ensure_list_csv(value)
    if any(" " in target for target in targets):
        raise vol.Invalid("values should not contain spaces")
    return value


def has_at_least_one_target_kind(conf: dict[str, Any]) -> dict[str, Any]:
    """Validate config has at least one target kind."""
    if FIELD_TARGET_USERNAME not in conf and FIELD_TARGET_ID not in conf:
        raise vol.Invalid(
            "You should specify at least one target_id or target_username"
        )
    return conf


def has_one_target_kind(conf: dict[str, Any]) -> dict[str, Any]:
    """Validate config has only one target kind."""
    error_msg = "You should specify either target_id or target_username but not both"
    if FIELD_TARGET_USERNAME in conf and FIELD_TARGET_ID in conf:
        raise vol.Invalid(error_msg)
    if FIELD_TARGET_USERNAME not in conf and FIELD_TARGET_ID not in conf:
        raise vol.Invalid(error_msg)
    return conf


def has_no_more_than_one_keyboard_kind(conf: dict[str, Any]) -> dict[str, Any]:
    """Validate config has not more than one keyboard kind."""
    if FIELD_KEYBOARD in conf and FIELD_INLINE_KEYBOARD in conf:
        raise vol.Invalid("You can't specify both keyboard and keyboard_inline")
    return conf


def date_is_in_future(value: datetime | None) -> datetime | None:
    """Validate date is in future."""
    if value is None:
        return None
    value = dt_util.as_local(value)
    if value <= dt_util.now():
        raise vol.Invalid("Schedule date should be in future")
    return value


def allow_keyboard_resize_if_keyboard_defined(conf: dict[str, Any]) -> dict[str, Any]:
    """Validate config doesn't have keyboard_resize if keyboard not defined."""
    if FIELD_KEYBOARD_RESIZE in conf and FIELD_KEYBOARD not in conf:
        raise vol.Invalid("You can't specify keyboard_resize without defining keyboard")
    return conf


def allow_keyboard_single_use_if_keyboard_defined(
    conf: dict[str, Any],
) -> dict[str, Any]:
    """Validate config doesn't have keyboard_single_use if keyboard not defined."""
    if FIELD_KEYBOARD_SINGLE_USE in conf and FIELD_KEYBOARD not in conf:
        raise vol.Invalid(
            "You can't specify keyboard_single_use without defining keyboard"
        )
    return conf


def allow_nosound_video_if_file_defined(conf: dict[str, Any]) -> dict[str, Any]:
    """Validate config doesn't have nosound_video if file not defined."""
    if FIELD_NOSOUND_VIDEO in conf and FIELD_FILE not in conf:
        raise vol.Invalid("You can't specify nosound_video without defining file")
    return conf


def allow_keyboard_if_file_not_defined(conf: dict[str, Any]) -> dict[str, Any]:
    """Validate config doesn't have keyboard or inline_keyboard if file defined."""
    if FIELD_FILE in conf and (FIELD_KEYBOARD in conf or FIELD_INLINE_KEYBOARD in conf):
        raise vol.Invalid(
            "You can't specify keyboard or inline_keyboard with defined file"
        )
    return conf
