"""Offer time listening automation rules."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change

# mypy: allow-untyped-defs, no-check-untyped-defs

CONF_HOURS = "hours"
CONF_MINUTES = "minutes"
CONF_SECONDS = "seconds"

_LOGGER = logging.getLogger(__name__)


class TimePattern:
    """Limit a value to a time pattern.

    :raises Invalid: If the value has a wrong format or is outside the range.
    """

    def __init__(self, max):
        self.max = max

    def __call__(self, v):
        try:
            value = str(v)
            if value == "*":
                return v
            if value[0] == "/":
                value = int(value[1:])
            else:
                value = int(value)

            if not (0 <= value <= self.max):
                raise vol.Invalid(f"must be a value between 0 and {self.max}")
        except ValueError:
            raise vol.Invalid(f"invalid time_pattern value")

        return v


TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): "time_pattern",
            CONF_HOURS: TimePattern(max=23),
            CONF_MINUTES: TimePattern(max=59),
            CONF_SECONDS: TimePattern(max=59),
        }
    ),
    cv.has_at_least_one_key(CONF_HOURS, CONF_MINUTES, CONF_SECONDS),
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    hours = config.get(CONF_HOURS)
    minutes = config.get(CONF_MINUTES)
    seconds = config.get(CONF_SECONDS)

    # If larger units are specified, default the smaller units to zero
    if minutes is None and hours is not None:
        minutes = 0
    if seconds is None and minutes is not None:
        seconds = 0

    @callback
    def time_automation_listener(now):
        """Listen for time changes and calls action."""
        hass.async_run_job(
            action, {"trigger": {"platform": "time_pattern", "now": now}}
        )

    return async_track_time_change(
        hass, time_automation_listener, hour=hours, minute=minutes, second=seconds
    )
