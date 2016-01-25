""" Event Decorators for custom components """

import functools

from homeassistant.helpers import event

HASS = None


def _callback(action, *args, **kwargs):
    """ adds HASS to callback arguments """
    action(HASS, *args, **kwargs)


def service(domain, service_name):
    """ Decorator factory to register a service """

    def register_service_decorator(action):
        """ Decorator to register a service """
        HASS.services.register(domain, service_name,
                               functools.partial(_callback, action))
        return action

    return register_service_decorator


def track_state_change(entity_ids, from_state=None, to_state=None):
    """ Decorator factory to track state changes for entity id """

    def track_state_change_decorator(action):
        """ Decorator to track state changes """
        event.track_state_change(HASS, entity_ids,
                                 functools.partial(_callback, action),
                                 from_state, to_state)
        return action

    return track_state_change_decorator


def track_sunrise(offset=None):
    """ Decorator factory to track sunrise events """

    def track_sunrise_decorator(action):
        """ Decorator to track sunrise events """
        event.track_sunrise(HASS,
                            functools.partial(_callback, action),
                            offset)
        return action

    return track_sunrise_decorator


def track_sunset(offset=None):
    """ Decorator factory to track sunset events """

    def track_sunset_decorator(action):
        """ Decorator to track sunset events """
        event.track_sunset(HASS,
                           functools.partial(_callback, action),
                           offset)
        return action

    return track_sunset_decorator


# pylint: disable=too-many-arguments
def track_time_change(year=None, month=None, day=None, hour=None, minute=None,
                      second=None):
    """ Decorator factory to track time changes """

    def track_time_change_decorator(action):
        """ Decorator to track time changes """
        event.track_time_change(HASS,
                                functools.partial(_callback, action),
                                year, month, day, hour, minute, second)
        return action

    return track_time_change_decorator


# pylint: disable=too-many-arguments
def track_utc_time_change(year=None, month=None, day=None, hour=None,
                          minute=None, second=None):
    """ Decorator factory to track time changes """

    def track_utc_time_change_decorator(action):
        """ Decorator to track time changes """
        event.track_utc_time_change(HASS,
                                    functools.partial(_callback, action),
                                    year, month, day, hour, minute, second)
        return action

    return track_utc_time_change_decorator
