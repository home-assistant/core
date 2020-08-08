"""Offer time listening automation rules."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_AT, CONF_PLATFORM
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "time",
        vol.Required(CONF_AT): vol.All(cv.ensure_list, [cv.time]),
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    at_times = config[CONF_AT]

    @callback
    def time_automation_listener(now):
        """Listen for time changes and calls action."""
        hass.async_run_job(action, {"trigger": {"platform": "time", "now": now}})

    removes = [
        async_track_time_change(
            hass,
            time_automation_listener,
            hour=at_time.hour,
            minute=at_time.minute,
            second=at_time.second,
        )
        for at_time in at_times
    ]

    @callback
    def remove_track_time_changes():
        """Remove tracked time changes."""
        for remove in removes:
            remove()

    return remove_track_time_changes
