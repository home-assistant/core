""" Event Decorators for custom components """

from datetime import datetime
import functools
import inspect
import logging

from homeassistant.helpers import event
from homeassistant.components import logbook

REGISTERED_DECORATORS = []
_LOGGER = logging.getLogger(__name__)


def track_state_change(entity_ids, from_state=None, to_state=None):
    """ Decorator factory to track state changes for entity id """

    def track_state_change_decorator(action):
        """ Decorator to track state changes """
        return Automation(action, event.track_state_change,
                          {"entity_ids": entity_ids, "from_state": from_state,
                           "to_state": to_state})

    return track_state_change_decorator


def track_sunrise(offset=None):
    """ Decorator factory to track sunrise events """

    def track_sunrise_decorator(action):
        """ Decorator to track sunrise events """
        return Automation(action, event.track_sunrise, {"offset": offset})

    return track_sunrise_decorator


def track_sunset(offset=None):
    """ Decorator factory to track sunset events """

    def track_sunset_decorator(action):
        """ Decorator to track sunset events """
        return Automation(action, event.track_sunset, {"offset": offset})

    return track_sunset_decorator


# pylint: disable=too-many-arguments
def track_time_change(year=None, month=None, day=None, hour=None, minute=None,
                      second=None):
    """ Decorator factory to track time changes """

    def track_time_change_decorator(action):
        """ Decorator to track time changes """
        return Automation(action, event.track_time_change,
                          {"year": year, "month": month, "day": day,
                           "hour": hour, "minute": minute, "second": second})

    return track_time_change_decorator


def activate(hass):
    """ Activate all event decorators """
    Automation.hass = hass

    return all([rule.activate() for rule in REGISTERED_DECORATORS])


class Automation(object):
    """ Base Decorator for automation functions """

    hass = None

    def __init__(self, action, event, event_args):
        # store action and config
        self.action = action
        self._event = (event, event_args)
        self._activated = False
        self._last_run = None
        self._running = 0
        module = inspect.getmodule(action)
        self._domain = module.DOMAIN

        REGISTERED_DECORATORS.append(self)

        functools.update_wrapper(self, action)

    def __call__(self, *args, **kwargs):
        """ Call the action """
        if not self.activated:
            return

        self._running += 1

        _LOGGER.info('Executing %s', self.alias)
        logbook.log_entry(self.hass, self.alias, 'has been triggered',
                          self._domain)

        try:
            self.action(*args, **kwargs)
        except Exception:
            _LOGGER.exception('Error running Python automation: %s',
                              self.alias)
        else:
            self._last_run = datetime.now()

        self._running -= 1

    @property
    def alias(self):
        """ The name of the action """
        return self.action.__name__

    @property
    def domain(self):
        """ The domain to which this automation belongs """
        return self._domain

    @property
    def is_running(self):
        """ Boolean if the automation is running """
        return self._running > 0

    @property
    def num_running(self):
        """ Integer of how many instances of the automation are running """
        return self._running

    @property
    def activated(self):
        """ Boolean indicating if the automation has been activated """
        return self._activated

    @property
    def last_run(self):
        """ Datetime object of the last automation completion """
        return self._last_run

    def activate(self):
        """ Activates the automation with HASS """
        if self.activated:
            return True

        self._event[0](hass=self.hass, action=self.action, **self._event[1])

        self._activated = True
        return True
