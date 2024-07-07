"""Helper functions."""

from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant.util import dt as dt_util

from .const import ATTR_TARGET_ID, ATTR_TARGET_USERNAME


def has_only_one_target_kind(conf: dict[str, Any]) -> dict[str, Any]:
    """Validate config has only one target kind."""
    error_msg = "You should specify either target_id or target_username but not both"
    if ATTR_TARGET_USERNAME in conf and ATTR_TARGET_ID in conf:
        raise vol.Invalid(error_msg)
    if ATTR_TARGET_USERNAME not in conf and ATTR_TARGET_ID not in conf:
        raise vol.Invalid(error_msg)
    return conf


def date_is_in_future(value: datetime | None) -> datetime | None:
    """Validate date is in future."""
    if value is None:
        return None
    value = dt_util.as_local(value)
    if value <= dt_util.now():
        raise vol.Invalid("Schedule date should be in future")
    return value
