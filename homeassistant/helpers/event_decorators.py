"""Event Decorators for custom components."""
import functools
import logging

# pylint: disable=unused-import
from typing import Optional  # NOQA

from homeassistant.core import HomeAssistant  # NOQA
from homeassistant.helpers import event

HASS = None  # type: Optional[HomeAssistant]
_LOGGER = logging.getLogger(__name__)
_MSG = 'Event decorators are deprecated. Support will be removed in 0.40.'


def track_state_change(entity_ids, from_state=None, to_state=None):
    """Decorator factory to track state changes for entity id."""
    _LOGGER.warning(_MSG)

    def track_state_change_decorator(action):
        """Decorator to track state changes."""
        event.track_state_change(HASS, entity_ids,
                                 functools.partial(action, HASS),
                                 from_state, to_state)
        return action

    return track_state_change_decorator


def track_sunrise(offset=None):
    """Decorator factory to track sunrise events."""
    _LOGGER.warning(_MSG)

    def track_sunrise_decorator(action):
        """Decorator to track sunrise events."""
        event.track_sunrise(HASS,
                            functools.partial(action, HASS),
                            offset)
        return action

    return track_sunrise_decorator


def track_sunset(offset=None):
    """Decorator factory to track sunset events."""
    _LOGGER.warning(_MSG)

    def track_sunset_decorator(action):
        """Decorator to track sunset events."""
        event.track_sunset(HASS,
                           functools.partial(action, HASS),
                           offset)
        return action

    return track_sunset_decorator


def track_time_change(year=None, month=None, day=None, hour=None, minute=None,
                      second=None):
    """Decorator factory to track time changes."""
    _LOGGER.warning(_MSG)

    def track_time_change_decorator(action):
        """Decorator to track time changes."""
        event.track_time_change(HASS,
                                functools.partial(action, HASS),
                                year, month, day, hour, minute, second)
        return action

    return track_time_change_decorator


def track_utc_time_change(year=None, month=None, day=None, hour=None,
                          minute=None, second=None):
    """Decorator factory to track time changes."""
    _LOGGER.warning(_MSG)

    def track_utc_time_change_decorator(action):
        """Decorator to track time changes."""
        event.track_utc_time_change(HASS,
                                    functools.partial(action, HASS),
                                    year, month, day, hour, minute, second)
        return action

    return track_utc_time_change_decorator
