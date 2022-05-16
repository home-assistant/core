"""Helpers for the logger integration."""
import logging

from homeassistant.core import callback

from .const import DOMAIN, EVENT_LOGGING_CHANGED, LOGSEVERITY


@callback
def set_default_log_level(hass, level):
    """Set the default log level for components."""
    _set_log_level(logging.getLogger(""), level)
    hass.bus.async_fire(EVENT_LOGGING_CHANGED)


@callback
def set_log_levels(hass, logpoints):
    """Set the specified log levels."""
    hass.data[DOMAIN].update(logpoints)
    for key, value in logpoints.items():
        _set_log_level(logging.getLogger(key), value)
    hass.bus.async_fire(EVENT_LOGGING_CHANGED)


def _set_log_level(logger, level):
    """Set the log level.

    Any logger fetched before this integration is loaded will use old class.
    """
    getattr(logger, "orig_setLevel", logger.setLevel)(LOGSEVERITY[level])
