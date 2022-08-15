"""Offer time listening automation rules."""
import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

# mypy: allow-untyped-defs, no-check-untyped-defs

CONF_HOURS = "hours"
CONF_MINUTES = "minutes"
CONF_SECONDS = "seconds"


class TimePattern:
    """Validate a time pattern value.

    :raises Invalid: If the value has a wrong format or is outside the range.
    """

    def __init__(self, maximum):
        """Initialize time pattern."""
        self.maximum = maximum

    def __call__(self, value):
        """Validate input."""
        try:
            if value == "*":
                return value

            if isinstance(value, str) and value.startswith("/"):
                number = int(value[1:])
            else:
                value = number = int(value)

            if not (0 <= number <= self.maximum):
                raise vol.Invalid(f"must be a value between 0 and {self.maximum}")
        except ValueError as err:
            raise vol.Invalid("invalid time_pattern value") from err

        return value


TRIGGER_SCHEMA = vol.All(
    cv.TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_PLATFORM): "time_pattern",
            CONF_HOURS: TimePattern(maximum=23),
            CONF_MINUTES: TimePattern(maximum=59),
            CONF_SECONDS: TimePattern(maximum=59),
        }
    ),
    cv.has_at_least_one_key(CONF_HOURS, CONF_MINUTES, CONF_SECONDS),
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    hours = config.get(CONF_HOURS)
    minutes = config.get(CONF_MINUTES)
    seconds = config.get(CONF_SECONDS)
    job = HassJob(action)

    # If larger units are specified, default the smaller units to zero
    if minutes is None and hours is not None:
        minutes = 0
    if seconds is None and minutes is not None:
        seconds = 0

    @callback
    def time_automation_listener(now):
        """Listen for time changes and calls action."""
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    "platform": "time_pattern",
                    "now": now,
                    "description": "time pattern",
                }
            },
        )

    return async_track_time_change(
        hass, time_automation_listener, hour=hours, minute=minutes, second=seconds
    )
